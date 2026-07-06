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
