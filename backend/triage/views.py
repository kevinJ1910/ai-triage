from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import TriageSession, Transcription
from patients.models import Patient
from .ai_analyzer import analyze_triage_transcript
from transcription.whisper_engine import WhisperEngine
import uuid
import logging

logger = logging.getLogger(__name__)

class TriageSessionViewSet(viewsets.ModelViewSet):
    queryset = TriageSession.objects.all().order_by('-created_at')
    permission_classes = [AllowAny] # Set to IsAuthenticated when auth is fully implemented on frontend
    
    @action(detail=False, methods=['POST'])
    def analyze(self, request):
        """
        Receives audio file or text transcript, runs analysis, and saves the triage session.
        """
        transcript_text = request.data.get('transcript')
        audio_file = request.FILES.get('audio')
        
        if not transcript_text and not audio_file:
            return Response({"error": "No audio or transcript provided"}, status=status.HTTP_400_BAD_REQUEST)
            
        session_uuid = str(uuid.uuid4())
        
        if audio_file and not transcript_text:
            try:
                engine = WhisperEngine()
                audio_bytes = audio_file.read()
                result = engine.transcribe_chunk(audio_bytes, session_uuid)
                transcript_text = result.get('text', '')
            except Exception as e:
                logger.error(f"Whisper transcription failed: {e}")
                return Response({"error": "Transcription failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        # Analyze using Gemini
        analysis = analyze_triage_transcript(transcript_text)
        
        if "error" in analysis:
            return Response(analysis, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
        patient_info = analysis.get('patientInfo', {})
        triage_data = analysis.get('triage', {})
        entities = analysis.get('entities', {})
        confidence = analysis.get('confidence', None)
        
        # Upsert Patient
        document_id = patient_info.get('documentId')
        patient = None
        if document_id:
            patient, created = Patient.objects.get_or_create(
                document_id=document_id,
                defaults={
                    'full_name': patient_info.get('name'),
                    'birth_date': patient_info.get('birthDate') if patient_info.get('birthDate') else None,
                    'gender': patient_info.get('gender') or 'unknown',
                    'phone': patient_info.get('phone'),
                    'insurance': patient_info.get('insurance'),
                }
            )
        else:
            # Create an anonymous patient
            patient = Patient.objects.create(document_id=f"anon-{session_uuid[:8]}")
            
        # Create Session
        triage_session = TriageSession.objects.create(
            user=request.user if request.user.is_authenticated else None,
            patient=patient,
            level=triage_data.get('level', 5),
            justification=triage_data.get('justification', ''),
            clinical_entities=entities,
            confidence_score=confidence
        )
        
        # Create Transcription record
        Transcription.objects.create(
            triage_session=triage_session,
            session_uuid=session_uuid,
            full_text=transcript_text,
            model_used="whisper-gemini-2.5-flash"
        )
        
        return Response({
            "session_id": triage_session.id,
            "patient": {
                "id": patient.id,
                "document_id": patient.document_id,
                "name": patient.full_name
            },
            "transcript": transcript_text,
            "analysis": analysis
        }, status=status.HTTP_201_CREATED)

from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import random
import time

@csrf_exempt
@require_http_methods(["POST"])
def fhir_sync(request: HttpRequest) -> JsonResponse:
    """
    Simulates FHIR server synchronization, stores a FHIRRecord in the DB
    associated with the TriageSession if found, and returns 201.
    """
    try:
        payload = json.loads(request.body)
        # Simulate network delay (800ms)
        time.sleep(0.8)
        
        fhir_id = f"fhir-enc-{random.randint(100000, 999999)}"
        
        # Try to find associated session id from resource IDs like pat-<id> or enc-<id>
        session_id = None
        entries = payload.get('entry', [])
        for entry in entries:
            resource = entry.get('resource', {})
            res_id = resource.get('id', '')
            if res_id.startswith('enc-') or res_id.startswith('pat-'):
                parts = res_id.split('-')
                if len(parts) > 1 and parts[1].isdigit():
                    session_id = int(parts[1])
                    break
        
        if session_id:
            try:
                from .models import TriageSession, FHIRRecord
                triage_session = TriageSession.objects.filter(id=session_id).first()
                if triage_session:
                    FHIRRecord.objects.update_or_create(
                        triage_session=triage_session,
                        defaults={
                            'fhir_resource_id': fhir_id,
                            'payload_sent': payload
                        }
                    )
            except Exception as db_err:
                logger.error(f"Error saving FHIRRecord in database: {db_err}", exc_info=True)
                
        return JsonResponse({
            "message": "Resource created",
            "id": fhir_id,
            "resourceReceived": payload
        }, status=201)
        
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON FHIR payload"}, status=400)
    except Exception as e:
        logger.error(f"Error in fhir_sync: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error during FHIR sync", "details": str(e)}, status=500)

