from datetime import date
from django.db import transaction
from django.db.models import Avg, Count, F, FloatField, Q, Sum
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
from .models import TriageSession, Transcription, FHIRRecord, FHIRMessageLog
from patients.models import Patient
from accounts.models import AuditLog
from core.timeutils import local_strftime
from core.permissions import is_admin_user, user_has_flag, CanEditSymptoms, CanRegisterPatients, CanViewEMR, CanViewFHIR
from .tasks import analyze_with_worker
from .clinical_cache import ClinicalQueryCache
from .clinical_rag import ClinicalKnowledgeRAG
from .benchmark_results import load_results
from .blind_review_corpus import CORPUS_PREFIX
from .fhir_validation import validate_fhir_bundle
from .metrics import (
    confusion_matrix_from_counts, cohen_kappa, interpret_kappa,
    triage_safety_metrics_from_matrix, reference_agreement_from_matrix,
)
from core.task_runner import TaskUnavailable
from transcription.tasks import transcribe_audio
from transcription.whisper_engine import reset_session_context
import uuid
import logging

logger = logging.getLogger(__name__)

class TriageSessionViewSet(viewsets.GenericViewSet):
    """
    Solo expone acciones explicitas. No hereda list/retrieve/update/destroy:
    las sesiones de triaje no se borran ni se editan fuera de override_level.
    """
    queryset = TriageSession.objects.all().order_by('-created_at')
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['POST'], permission_classes=[IsAuthenticated, CanRegisterPatients])
    def analyze(self, request):
        """
        Receives audio file or text transcript, runs analysis, and saves the triage session.
        Supports explicit final_level override from client if sent.
        """
        transcript_text = (request.data.get('transcript') or '').strip()
        audio_file = request.FILES.get('audio')
        
        if not transcript_text and not audio_file:
            return Response({"error": "No audio or transcript provided"}, status=status.HTTP_400_BAD_REQUEST)
            
        session_uuid = str(uuid.uuid4())
        
        if audio_file and not transcript_text:
            try:
                result = transcribe_audio(audio_file.read(), session_uuid)
                transcript_text = (result.get('text') or '').strip()
            except TaskUnavailable:
                return Response({"error": "Servicio de transcripcion no disponible"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            except Exception as e:
                logger.error(f"Whisper transcription failed: {e}")
                return Response({"error": "Transcription failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            finally:
                # Audio completo de un solo envio: no hay continuidad que conservar.
                reset_session_context(session_uuid)
            if not transcript_text:
                # El audio llego pero no contenia voz reconocible: es un problema de la entrada, no del servidor.
                return Response({"error": "No se detecto voz en el audio enviado"}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
                
        # Analyze using Gemini or fallback
        analysis = analyze_with_worker(transcript_text)
        
        if "error" in analysis:
            # El analizador solo devuelve 'error' ante entradas no analizables; nunca por fallo del LLM.
            return Response(analysis, status=status.HTTP_400_BAD_REQUEST)
            
        patient_info = analysis.get('patientInfo', {})
        triage_data = analysis.get('triage', {})
        entities = analysis.get('entities', {})
        confidence = analysis.get('confidence', None)
        
        ai_level_val = triage_data.get('level', 5)
        # El cliente puede enviar un final_level confirmado; fuera de 1-5 se ignora.
        try:
            final_level_val = int(request.data.get('final_level', ai_level_val))
        except (ValueError, TypeError):
            final_level_val = ai_level_val
        if final_level_val not in range(1, 6):
            final_level_val = ai_level_val

        extracted_symptoms = entities.get('symptoms', []) if isinstance(entities, dict) else []

        # Paciente, sesion, transcripcion y auditoria se guardan juntos o no se guarda nada:
        # un triaje sin registro de auditoria no es aceptable.
        with transaction.atomic():
            patient = _upsert_patient(patient_info, session_uuid)

            triage_session = TriageSession.objects.create(
                user=request.user,
                patient=patient,
                level=final_level_val,
                ai_level=ai_level_val,
                final_level=final_level_val,
                is_level_modified=(final_level_val != ai_level_val),
                justification=triage_data.get('justification', ''),
                clinical_entities=entities,
                ai_symptoms=extracted_symptoms,
                final_symptoms=extracted_symptoms,
                confidence_score=confidence,
                prompt_tokens=analysis.get('prompt_tokens', 0),
                completion_tokens=analysis.get('completion_tokens', 0),
                total_tokens=analysis.get('total_tokens', 0),
                is_cached=analysis.get('cached', False),
                rag_context=analysis.get('rag_context', [])
            )

            Transcription.objects.create(
                triage_session=triage_session,
                session_uuid=session_uuid,
                full_text=transcript_text,
                model_used=(analysis.get('engine_used') or 'desconocido')[:100]
            )

            AuditLog.objects.create(
                user=request.user,
                action='TRIAGE_CREATED',
                resource=f'TriageSession #{triage_session.id}',
                details=f'Triaje inicial guardado. AI Nivel: {ai_level_val}, Final: {final_level_val}, Paciente: {patient.document_id}',
                ip_address=request.META.get('REMOTE_ADDR')
            )

        # Explicabilidad: los criterios del protocolo recuperados, con su texto (en la sesion solo se guardan los ids).
        analysis["rag_criteria"] = ClinicalKnowledgeRAG.describe(analysis.get('rag_context', []))

        return Response({
            "session_id": triage_session.id,
            "patient": {
                "id": patient.id,
                "document_id": patient.document_id,
                "name": patient.full_name
            },
            "transcript": transcript_text,
            "ai_level": ai_level_val,
            "final_level": final_level_val,
            "is_level_modified": triage_session.is_level_modified,
            "agreement_score": triage_session.agreement_score,
            "analysis": analysis,
            "warning": analysis.get('warning'),
            "protocol": analysis.get('protocol', 'Christus Sinergia Salud'),
            "engine_used": analysis.get('engine_used')
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['PATCH'], permission_classes=[IsAuthenticated, CanEditSymptoms])
    def override_level(self, request, pk=None):
        """
        Allows physician to manually override triage level (1 to 5) and symptom list.
        """
        session = self.get_object()
        from core.validation import validate_payload, TriageOverrideSchema
        try:
            validated = validate_payload(TriageOverrideSchema, request.data)
            new_level = validated.final_level
            override_reason = validated.override_reason or ''
            final_symptoms = validated.final_symptoms
        except Exception as e:
            return Response(getattr(e, 'detail', {"error": str(e)}), status=status.HTTP_400_BAD_REQUEST)

        old_level = session.final_level
        if validated.final_level is not None:
            new_level = validated.final_level
            session.final_level = new_level
            session.level = new_level
            session.is_level_modified = (session.final_level != session.ai_level)
            dist = abs(session.final_level - session.ai_level)
            session.agreement_score = max(0.0, 1.0 - (dist / 4.0))

        if validated.justification is not None and validated.justification.strip():
            session.justification = validated.justification.strip()
        elif override_reason:
            session.justification += f"\n[Ajuste Medico]: {override_reason}"

        if isinstance(final_symptoms, list):
            session.final_symptoms = final_symptoms

        session.save()

        # Audit Log
        try:
            AuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action='TRIAGE_OVERRIDE',
                resource=f'TriageSession #{session.id}',
                details=f'Nivel modificado de {old_level} a {new_level} (AI: {session.ai_level}). Motivo: {override_reason or "Revision clinica"}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
        except Exception as audit_err:
            logger.error(f"AuditLog write failed for TRIAGE_OVERRIDE: {audit_err}", exc_info=True)

        return Response({
            "message": "Nivel de triaje actualizado exitosamente",
            "session_id": session.id,
            "ai_level": session.ai_level,
            "final_level": session.final_level,
            "is_level_modified": session.is_level_modified,
            "agreement_score": session.agreement_score
        })

    @action(detail=False, methods=['GET'])
    def history(self, request):
        """
        Historial de triajes persistido en BD (reemplaza el guardado en localStorage del navegador).
        Cada usuario ve sus propias sesiones; un administrador ve todas.
        Devuelve la misma forma que consume TriageDashboard.
        """
        qs = (TriageSession.objects
              .exclude(patient__document_id__startswith=CORPUS_PREFIX)
              .select_related('patient', 'transcription')
              .order_by('-created_at'))
        if not is_admin_user(request.user):
            qs = qs.filter(user=request.user)
        try:
            limit = max(1, min(int(request.query_params.get('limit', 50)), 200))
        except (TypeError, ValueError):
            limit = 50

        entity_keys = ('symptoms', 'diagnoses', 'medications', 'allergies', 'vitals', 'history', 'negated_findings')
        results = []
        for s in qs[:limit]:
            pat = s.patient
            entities = s.clinical_entities if isinstance(s.clinical_entities, dict) else {}
            transcription = getattr(s, 'transcription', None)
            results.append({
                "id": str(s.id),
                "date": s.created_at.isoformat(),
                "patientName": pat.full_name or pat.document_id,
                "patientInfo": {
                    "name": pat.full_name or '',
                    "documentId": '' if pat.document_id.startswith('anon-') else pat.document_id,
                    "birthDate": pat.birth_date.isoformat() if pat.birth_date else '',
                    "gender": pat.gender or 'unknown',
                    "phone": pat.phone or '',
                    "insurance": pat.insurance or '',
                },
                "transcript": _split_transcript(transcription.full_text if transcription else ''),
                "analysisResult": {
                    "triage": {
                        "level": s.final_level,
                        "final_level": s.final_level,
                        "ai_level": s.ai_level,
                        "is_modified": s.is_level_modified,
                        "justification": s.justification,
                    },
                    "entities": {
                        **{k: entities.get(k, []) for k in entity_keys},
                        "symptoms": s.final_symptoms or entities.get('symptoms', []),
                    },
                    "confidence": s.confidence_score,
                    # Explicabilidad que se conserva: criterios del protocolo y motor. Los terminos normalizados
                    # y las menciones del NER no se guardan en la sesion.
                    "engine_used": transcription.model_used if transcription else None,
                    "rag_criteria": ClinicalKnowledgeRAG.describe(s.rag_context if isinstance(s.rag_context, list) else []),
                },
            })
        return Response(results)

    @action(detail=False, methods=['GET'])
    def evaluation_metrics(self, request):
        """
        Metricas de concordancia IA vs medico (referencia: nivel final ratificado):
        - Concordancia exacta, Kappa de Cohen ponderado cuadratico (escala ordinal) y sin ponderar
        - Infratriaje / sobretriaje y sensibilidad en casos criticos (niveles 1-2)
        - Matriz de confusion 5x5, deriva de severidad y retencion de sintomas
        Sin sesiones no se inventan valores: las metricas se devuelven como null.
        """
        # Agregaciones en la base de datos: no se cargan todas las sesiones en memoria. Los casos del corpus
        # cargados para la validacion ciega (CORPUS-) no son pacientes reales y se resumen con export_blind_review.

        qs = TriageSession.objects.exclude(patient__document_id__startswith=CORPUS_PREFIX).order_by()
        matrix = _level_matrix(qs, 'ai_level', 'final_level')
        dist_ai = {lvl: sum(matrix[lvl - 1]) for lvl in range(1, 6)}
        dist_phy = {lvl: sum(row[lvl - 1] for row in matrix) for lvl in range(1, 6)}

        totals = qs.aggregate(
            total=Count('id'),
            modified=Count('id', filter=Q(is_level_modified=True)),
            drift=Avg(F('final_level') - F('ai_level'), output_field=FloatField()),
            tokens=Sum('total_tokens'),
            cached=Count('id', filter=Q(is_cached=True)),
        )
        total = totals['total']
        modified_count = totals['modified']
        concordant_count = total - modified_count

        kappa_weighted = cohen_kappa(matrix, weights='quadratic')
        kappa_unweighted = cohen_kappa(matrix, weights='none')

        concordance_rate = severity_drift = symptom_retention = None
        if total:
            concordance_rate = round((concordant_count / total) * 100, 1)
            severity_drift = round(totals['drift'], 2)

            # La interseccion de listas JSON no es portable en SQL: se recorre por lotes solo con esas columnas.
            retention_sum = 0.0
            for ai_symptoms, final_symptoms in qs.values_list('ai_symptoms', 'final_symptoms').iterator(chunk_size=1000):
                ai_s = {str(x).lower() for x in (ai_symptoms or [])}
                fin_s = {str(x).lower() for x in (final_symptoms or [])}
                retention_sum += 1.0 if not ai_s else len(ai_s & fin_s) / len(ai_s)
            symptom_retention = round((retention_sum / total) * 100, 1)

        rated = qs.filter(justification_rated_at__isnull=False).aggregate(
            n=Count('id'), clarity=Avg('justification_clarity'), relevance=Avg('justification_relevance'),
            fidelity=Avg('justification_fidelity'),
        )
        justification_ratings = {
            "n": rated['n'],
            **{key: (round(rated[key], 2) if rated[key] is not None else None) for key in ('clarity', 'relevance', 'fidelity')},
        }

        referenced = qs.filter(reference_level__isnull=False)
        ai_vs_reference = _level_matrix(referenced, 'ai_level', 'reference_level')
        physician_vs_reference = _level_matrix(referenced, 'final_level', 'reference_level')

        # Las metricas son agregadas y visibles para todo el personal; la identidad del paciente
        # solo se muestra a quien ya puede consultar la HCE.
        can_see_identity = user_has_flag(request.user, 'can_view_emr')
        recent = [{
            "id": s.id,
            "patient": (s.patient.full_name or s.patient.document_id) if can_see_identity else f"Paciente #{s.patient_id}",
            "ai_level": s.ai_level,
            "final_level": s.final_level,
            "is_modified": s.is_level_modified,
            "agreement_score": round(s.agreement_score * 100, 1),
            "date": local_strftime(s.created_at, '%Y-%m-%d %H:%M')
        } for s in qs.select_related('patient').order_by('-created_at')[:10]]

        return Response({
            "total_triages": total,
            "concordance_rate": concordance_rate,
            "severity_drift": severity_drift,
            "symptom_retention": symptom_retention,
            "cohen_kappa": kappa_weighted,
            "cohen_kappa_unweighted": kappa_unweighted,
            "kappa_type": "quadratic_weighted",
            "kappa_interpretation": interpret_kappa(kappa_weighted),
            **triage_safety_metrics_from_matrix(matrix),
            "confusion_matrix": matrix,
            "modified_count": modified_count,
            "unmodified_count": concordant_count,
            "distribution_ai": dist_ai,
            "distribution_physician": dist_phy,
            "total_tokens_consumed": totals['tokens'] or 0,
            "cached_triages_count": totals['cached'],
            "clinical_cache_stats": ClinicalQueryCache.stats(),
            "recent_evaluations": recent,
            "justification_ratings": justification_ratings,
            # Validacion contra el nivel de referencia ciego: es la medida sin sesgo de anclaje.
            "reference_validation": {
                "referenced_count": sum(map(sum, ai_vs_reference)),
                "ai_vs_reference": reference_agreement_from_matrix(ai_vs_reference),
                "physician_vs_reference": reference_agreement_from_matrix(physician_vs_reference),
            },
        })

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated, CanEditSymptoms])
    def blind_review_queue(self, request):
        """
        Casos pendientes de adjudicacion ciega. Solo expone la transcripcion y datos demograficos
        minimos: nunca el nivel de la IA, el nivel final, la justificacion ni el contexto RAG.
        Se excluyen los triajes realizados por el propio adjudicador.
        """
        qs = (TriageSession.objects
              .filter(reference_level__isnull=True)
              .exclude(user=request.user)
              .select_related('patient', 'transcription')
              .order_by('created_at'))
        pending_total = qs.count()
        adjudicated_by_me = TriageSession.objects.filter(reference_by=request.user).count()
        rated_by_me = TriageSession.objects.filter(
            reference_by=request.user,
            justification_rated_at__isnull=False,
        ).count()
        results = []
        for s in qs[:20]:
            transcription = getattr(s, 'transcription', None)
            birth_date = s.patient.birth_date
            age = None
            if birth_date:
                ref = s.created_at.date()
                age = ref.year - birth_date.year - ((ref.month, ref.day) < (birth_date.month, birth_date.day))
            results.append({
                "id": s.id,
                "date": local_strftime(s.created_at, '%Y-%m-%d %H:%M'),
                "gender": s.patient.gender or 'unknown',
                "age": age,
                "transcript": transcription.full_text if transcription else '',
            })
        return Response({
            "pending_total": pending_total,
            "adjudicated_by_me": adjudicated_by_me,
            "rated_by_me": rated_by_me,
            "results": results,
        })

    @action(detail=True, methods=['POST'], permission_classes=[IsAuthenticated, CanEditSymptoms])
    def reference_level(self, request, pk=None):
        """
        Registra el nivel de referencia ciego. Es inmutable: una vez adjudicado no se reescribe,
        y el clinico que hizo el triaje no puede adjudicarlo.
        """
        from core.validation import validate_payload, TriageReferenceSchema
        validated = validate_payload(TriageReferenceSchema, request.data)

        with transaction.atomic():
            session = TriageSession.objects.select_for_update().get(pk=self.get_object().pk)
            if session.user_id is not None and session.user_id == request.user.id:
                return Response({"error": "No puede adjudicar un triaje realizado por usted"}, status=status.HTTP_403_FORBIDDEN)
            if session.reference_level is not None:
                return Response({"error": "Este triaje ya tiene nivel de referencia"}, status=status.HTTP_409_CONFLICT)

            session.reference_level = validated.reference_level
            session.reference_by = request.user
            session.reference_at = timezone.now()
            session.save(update_fields=['reference_level', 'reference_by', 'reference_at'])

            AuditLog.objects.create(
                user=request.user,
                action='TRIAGE_REFERENCE',
                resource=f'TriageSession #{session.id}',
                details=f'Nivel de referencia ciego registrado: {session.reference_level}',
                ip_address=request.META.get('REMOTE_ADDR')
            )

        # Fijada la referencia, el adjudicador ya puede ver la justificacion de la IA para valorarla (Likert).
        return Response({"session_id": session.id, "reference_level": session.reference_level,
                         "justification": session.justification})

    @action(detail=True, methods=['POST'], permission_classes=[IsAuthenticated, CanEditSymptoms])
    def justification_rating(self, request, pk=None):
        """
        Valoracion Likert de la justificacion de la IA. Solo la registra quien adjudico la referencia,
        despues de fijarla (asi no influye en el nivel ciego), y una sola vez.
        """
        from core.validation import validate_payload, JustificationRatingSchema
        validated = validate_payload(JustificationRatingSchema, request.data)

        with transaction.atomic():
            session = TriageSession.objects.select_for_update().get(pk=self.get_object().pk)
            if session.reference_level is None or session.reference_by_id != request.user.id:
                return Response({"error": "Solo quien adjudicó la referencia puede valorar la justificación"},
                                status=status.HTTP_403_FORBIDDEN)
            if session.justification_rated_at is not None:
                return Response({"error": "La justificación de este triaje ya fue valorada"}, status=status.HTTP_409_CONFLICT)

            session.justification_clarity = validated.clarity
            session.justification_relevance = validated.relevance
            session.justification_fidelity = validated.fidelity
            session.justification_rated_at = timezone.now()
            session.save(update_fields=['justification_clarity', 'justification_relevance',
                                        'justification_fidelity', 'justification_rated_at'])

            AuditLog.objects.create(
                user=request.user,
                action='TRIAGE_JUSTIFICATION_RATING',
                resource=f'TriageSession #{session.id}',
                details=(f'Valoracion de la justificacion: claridad {validated.clarity}, '
                         f'pertinencia {validated.relevance}, fidelidad {validated.fidelity}'),
                ip_address=request.META.get('REMOTE_ADDR')
            )

        return Response({"session_id": session.id, "clarity": validated.clarity,
                         "relevance": validated.relevance, "fidelity": validated.fidelity})

    @action(detail=False, methods=['GET'])
    def benchmark_results(self, request):
        """Resultados reproducibles guardados por evaluate_extraction/evaluate_benchmark y evaluate_asr."""
        return Response(load_results())

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated, CanViewEMR])
    def emr_patients(self, request):
        """
        Returns patients list from real database for the EMR simulator.
        Reads persisted assigned_box and care_status.
        """
        sessions = (TriageSession.objects
                    .exclude(patient__document_id__startswith=CORPUS_PREFIX)
                    .select_related('patient')
                    .order_by('-created_at')[:20])
        results = []

        for s in sessions:
            pat = s.patient
            entities = s.clinical_entities or {}

            results.append({
                "id": s.id,
                "patient_id": pat.id,
                "document_id": pat.document_id,
                "name": pat.full_name or f"Paciente {pat.document_id}",
                "gender": pat.gender,
                "birth_date": pat.birth_date,
                "phone": pat.phone or "N/A",
                "insurance": pat.insurance,
                "level": s.final_level,
                "ai_level": s.ai_level,
                # Solo se informa la ubicacion realmente asignada (assign_box); nunca se inventa.
                "assigned_box": s.assigned_box,
                "status": s.care_status,
                "admission_time": local_strftime(s.created_at, '%H:%M:%S'),
                "justification": s.justification,
                "entities": entities
            })

        return Response(results)

    @action(detail=True, methods=['POST'], permission_classes=[IsAuthenticated, CanViewEMR])
    def assign_box(self, request, pk=None):
        """
        Assigns a hospital box/bed to a triage session patient.
        Validates payload with EMRBoxAssignSchema and persists assigned_box / care_status.
        """
        session = self.get_object()
        from core.validation import validate_payload, EMRBoxAssignSchema
        validated = validate_payload(EMRBoxAssignSchema, request.data)

        box = validated.assigned_box
        status_str = validated.status or 'En Atencion'

        session.assigned_box = box
        session.care_status = status_str
        session.save(update_fields=['assigned_box', 'care_status'])

        AuditLog.objects.create(
            user=request.user,
            action="EMR_BOX_ASSIGNED",
            resource=f"TriageSession:{session.id}",
            status="SUCCESS",
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            details=f"Box asignado: {box} al paciente {session.patient.document_id}"
        )

        return Response({
            "message": f"Box {box} asignado exitosamente",
            "session_id": session.id,
            "patient_id": session.patient.id,
            "assigned_box": box,
            "status": status_str
        })

    @action(detail=True, methods=['POST'], permission_classes=[IsAuthenticated, CanViewEMR])
    def release_box(self, request, pk=None):
        """
        Libera el box asignado al paciente y actualiza su estado asistencial
        (por defecto 'Alta Medica').
        """
        session = self.get_object()
        status_str = request.data.get('status', 'Alta Medica')
        old_box = session.assigned_box or 'Sin Box'
        session.assigned_box = ''
        session.care_status = status_str
        session.save(update_fields=['assigned_box', 'care_status'])

        AuditLog.objects.create(
            user=request.user,
            action="EMR_BOX_RELEASED",
            resource=f"TriageSession:{session.id}",
            status="SUCCESS",
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            details=f"Box {old_box} liberado. Estado: {status_str} (Paciente {session.patient.document_id})"
        )

        return Response({
            "message": f"Box {old_box} liberado exitosamente. Estado: {status_str}",
            "session_id": session.id,
            "patient_id": session.patient.id,
            "assigned_box": "",
            "status": status_str
        })

    @action(detail=True, methods=['POST', 'PATCH'], permission_classes=[IsAuthenticated, CanViewEMR])
    def update_care_status(self, request, pk=None):
        """
        Actualiza el estado asistencial del paciente y notas de evolucion clinica en el simulador HCE.
        """
        session = self.get_object()
        status_str = request.data.get('status')
        evolution_notes = request.data.get('evolution_notes')

        update_fields = []
        if status_str:
            session.care_status = status_str
            update_fields.append('care_status')

        if evolution_notes is not None:
            entities = session.clinical_entities or {}
            entities['evolution_notes'] = evolution_notes
            session.clinical_entities = entities
            update_fields.append('clinical_entities')

        if update_fields:
            session.save(update_fields=update_fields)

        AuditLog.objects.create(
            user=request.user,
            action="EMR_CARE_STATUS_UPDATED",
            resource=f"TriageSession:{session.id}",
            status="SUCCESS",
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            details=f"Estado asistencial actualizado a '{session.care_status}' (Paciente {session.patient.document_id})"
        )

        return Response({
            "message": "Ficha clinica actualizada exitosamente.",
            "session_id": session.id,
            "patient_id": session.patient.id,
            "status": session.care_status,
            "evolution_notes": (session.clinical_entities or {}).get('evolution_notes', '')
        })

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated, CanViewEMR])
    def boxes_census(self, request):
        """
        Retorna el censo hospitalario de boxes y camillas con ocupacion en tiempo real.
        """
        from django.core.cache import cache
        custom_boxes = cache.get('emr_custom_boxes') or []
        deleted_boxes = set(cache.get('emr_deleted_boxes') or [])
        box_states = cache.get('emr_box_operational_states') or {}

        default_boxes = [
            {"code": "REAN-01", "area": "Reanimacion", "type": "Box Vital", "equipment": "Monitor invasivo, Desfibrilador, Ventilador"},
            {"code": "REAN-02", "area": "Reanimacion", "type": "Box Vital", "equipment": "Monitor invasivo, Carro de paro"},
            {"code": "BOX-01", "area": "Boxes Generales", "type": "Camilla Urgencias", "equipment": "Monitor de signos vitales, Oxigeno"},
            {"code": "BOX-02", "area": "Boxes Generales", "type": "Camilla Urgencias", "equipment": "Monitor de signos vitales, Oxigeno"},
            {"code": "BOX-03", "area": "Boxes Generales", "type": "Camilla Urgencias", "equipment": "Monitor de signos vitales, Oxigeno"},
            {"code": "BOX-04", "area": "Boxes Generales", "type": "Camilla Urgencias", "equipment": "Monitor de signos vitales"},
            {"code": "BOX-05", "area": "Boxes Generales", "type": "Camilla Urgencias", "equipment": "Monitor de signos vitales"},
            {"code": "BOX-06", "area": "Boxes Generales", "type": "Camilla Urgencias", "equipment": "Monitor de signos vitales"},
            {"code": "SALA-OBSERVACION", "area": "Observacion", "type": "Cama Hospitalaria", "equipment": "Toma de oxigeno, Succion"},
            {"code": "AISL-01", "area": "Aislamiento", "type": "Box Presion Negativa", "equipment": "Filtro HEPA, Monitor de signos"},
        ]

        all_boxes_dict = {b["code"]: b for b in default_boxes if b["code"] not in deleted_boxes}
        for cb in custom_boxes:
            if cb["code"] not in deleted_boxes:
                all_boxes_dict[cb["code"]] = cb

        active_sessions = (TriageSession.objects
                           .exclude(assigned_box='')
                           .exclude(care_status__icontains='Alta')
                           .select_related('patient')
                           .order_by('-created_at'))

        occupied_map = {}
        for s in active_sessions:
            if s.assigned_box not in occupied_map:
                occupied_map[s.assigned_box] = {
                    "session_id": s.id,
                    "patient_id": s.patient.id,
                    "patient_name": s.patient.full_name or f"Paciente {s.patient.document_id}",
                    "document_id": s.patient.document_id,
                    "triage_level": s.final_level,
                    "care_status": s.care_status,
                    "admission_time": local_strftime(s.created_at, '%H:%M:%S'),
                }

        results = []
        for code, b in all_boxes_dict.items():
            occupant = occupied_map.get(code)
            operational_state = box_states.get(code, 'Libre')

            if occupant:
                status_val = 'Ocupado'
            elif operational_state == 'En Desinfeccion':
                status_val = 'En Desinfeccion'
            elif operational_state == 'Mantenimiento':
                status_val = 'Mantenimiento'
            else:
                status_val = 'Libre'

            results.append({
                "code": code,
                "area": b.get("area", "Boxes Generales"),
                "type": b.get("type", "Camilla Urgencias"),
                "equipment": b.get("equipment", ""),
                "status": status_val,
                "occupant": occupant,
                "is_custom": b.get("is_custom", False)
            })

        total = len(results)
        occupied_count = sum(1 for r in results if r["status"] == "Ocupado")
        cleaning_count = sum(1 for r in results if r["status"] == "En Desinfeccion")
        available_count = sum(1 for r in results if r["status"] == "Libre")

        return Response({
            "boxes": results,
            "summary": {
                "total": total,
                "occupied": occupied_count,
                "available": available_count,
                "cleaning": cleaning_count,
                "occupancy_rate": round((occupied_count / total * 100) if total > 0 else 0, 1)
            }
        })

    @action(detail=False, methods=['POST'], permission_classes=[IsAuthenticated, CanViewEMR])
    def manage_boxes(self, request):
        """
        Permite registrar, actualizar o eliminar boxes hospitalarios y sus estados operativos.
        """
        from django.core.cache import cache
        action_type = request.data.get('action')

        if action_type == 'create':
            code = (request.data.get('code') or '').strip().upper()
            if not code:
                return Response({"error": "El codigo de box es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
            area = request.data.get('area', 'Boxes Generales')
            box_type = request.data.get('type', 'Camilla Urgencias')
            equipment = request.data.get('equipment', '')

            custom_boxes = cache.get('emr_custom_boxes') or []
            if any(b["code"] == code for b in custom_boxes):
                return Response({"error": f"El box {code} ya existe."}, status=status.HTTP_400_BAD_REQUEST)

            deleted_boxes = cache.get('emr_deleted_boxes') or []
            if code in deleted_boxes:
                deleted_boxes = [c for c in deleted_boxes if c != code]
                cache.set('emr_deleted_boxes', deleted_boxes, timeout=None)

            new_box = {
                "code": code,
                "area": area,
                "type": box_type,
                "equipment": equipment,
                "is_custom": True
            }
            custom_boxes.append(new_box)
            cache.set('emr_custom_boxes', custom_boxes, timeout=None)
            return Response({"message": f"Box {code} creado exitosamente.", "box": new_box}, status=status.HTTP_201_CREATED)

        elif action_type in ('update', 'edit'):
            code = (request.data.get('code') or '').strip().upper()
            if not code:
                return Response({"error": "El codigo de box es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
            area = request.data.get('area')
            box_type = request.data.get('type')
            equipment = request.data.get('equipment')

            custom_boxes = cache.get('emr_custom_boxes') or []
            found = False
            for b in custom_boxes:
                if b["code"] == code:
                    if area: b["area"] = area
                    if box_type: b["type"] = box_type
                    if equipment is not None: b["equipment"] = equipment
                    found = True
                    break

            if not found:
                custom_boxes.append({
                    "code": code,
                    "area": area or "Boxes Generales",
                    "type": box_type or "Camilla Urgencias",
                    "equipment": equipment or "",
                    "is_custom": True
                })

            cache.set('emr_custom_boxes', custom_boxes, timeout=None)
            return Response({"message": f"Box {code} actualizado exitosamente."})

        elif action_type == 'update_state':
            code = (request.data.get('code') or '').strip().upper()
            new_state = request.data.get('state', 'Libre')
            box_states = cache.get('emr_box_operational_states') or {}
            box_states[code] = new_state
            cache.set('emr_box_operational_states', box_states, timeout=None)
            return Response({"message": f"Estado del box {code} actualizado a {new_state}."})

        elif action_type == 'delete':
            code = (request.data.get('code') or '').strip().upper()
            if not code:
                return Response({"error": "El codigo de box es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
            custom_boxes = cache.get('emr_custom_boxes') or []
            custom_boxes = [b for b in custom_boxes if b["code"] != code]
            cache.set('emr_custom_boxes', custom_boxes, timeout=None)

            deleted_boxes = cache.get('emr_deleted_boxes') or []
            if code not in deleted_boxes:
                deleted_boxes.append(code)
                cache.set('emr_deleted_boxes', deleted_boxes, timeout=None)
            return Response({"message": f"Box {code} eliminado exitosamente."})

        return Response({"error": "Accion no reconocida."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['GET'], permission_classes=[IsAuthenticated, CanViewFHIR])
    def fhir_logs(self, request):
        """
        Returns audit logs of FHIR R4 transactions.
        """
        logs = FHIRMessageLog.objects.all().order_by('-created_at')[:50]
        data = []
        for l in logs:
            data.append({
                "id": l.id,
                "session_id": l.session_id,
                "resource_type": l.resource_type,
                "direction": l.direction,
                "status_code": l.status_code,
                "fhir_resource_id": l.fhir_resource_id,
                "validation_status": l.validation_status,
                "validation_details": l.validation_details,
                "payload": l.payload,
                "created_at": local_strftime(l.created_at, '%Y-%m-%d %H:%M:%S')
            })
        return Response(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def fhir_sync(request) -> JsonResponse:
    """
    Simula la sincronizacion con un servidor FHIR: valida la estructura R4 del Bundle,
    registra la transaccion en FHIRMessageLog y, si es valido, guarda el FHIRRecord.
    JSON malformado -> 400 (parser DRF); esquema base invalido -> 400; Bundle R4 invalido -> 422.
    """
    payload = request.data
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Invalid JSON FHIR payload"}, status=400)

    from core.validation import validate_payload, FHIRSyncSchema
    validate_payload(FHIRSyncSchema, payload)

    is_valid, validation_details = validate_fhir_bundle(payload)
    triage_session = _find_session_in_bundle(payload)
    fhir_id = f"fhir-enc-{uuid.uuid4()}" if is_valid else ""
    status_code = 201 if is_valid else 422

    try:
        if is_valid and triage_session:
            FHIRRecord.objects.update_or_create(
                triage_session=triage_session,
                defaults={'fhir_resource_id': fhir_id, 'payload_sent': payload}
            )
        FHIRMessageLog.objects.create(
            session=triage_session,
            resource_type=payload.get('resourceType', 'Bundle'),
            direction='OUTBOUND',
            status_code=status_code,
            fhir_resource_id=fhir_id,
            validation_status='VALID' if is_valid else 'ERROR',
            validation_details=validation_details,
            payload=payload
        )
    except Exception as e:
        logger.error(f"Error in fhir_sync: {e}", exc_info=True)
        return JsonResponse({"error": "Internal server error during FHIR sync"}, status=500)

    if not is_valid:
        return JsonResponse({"error": "Bundle FHIR R4 invalido", "details": validation_details}, status=422)

    return JsonResponse({
        "message": "Resource created",
        "id": fhir_id,
        "validation": validation_details,
        "resourceReceived": payload
    }, status=201)


def _find_session_in_bundle(payload) -> "TriageSession | None":
    """Localiza la sesion de triaje por los ids 'enc-<id>' / 'pat-<id>' del Bundle."""
    for entry in payload.get('entry') or []:
        resource = entry.get('resource', {}) if isinstance(entry, dict) else {}
        res_id = str(resource.get('id', ''))
        if res_id.startswith(('enc-', 'pat-')):
            parts = res_id.split('-')
            if len(parts) > 1 and parts[1].isdigit():
                candidate_id = int(parts[1])
                if 0 < candidate_id <= 2147483647:
                    return TriageSession.objects.filter(id=candidate_id).first()
    return None


def _parse_iso_date(value):
    """Fecha YYYY-MM-DD o None: un valor mal formado del LLM no debe romper el guardado."""
    try:
        return date.fromisoformat(str(value)) if value else None
    except ValueError:
        return None


def _upsert_patient(patient_info: dict, session_uuid: str) -> Patient:
    """
    Busca el paciente por documento. Si ya existe, solo completa los campos vacios:
    nunca sobrescribe datos registrados con lo que extrajo la IA.
    Sin documento se crea un paciente anonimo propio de esta sesion.
    """
    document_id = patient_info.get('documentId')
    if not document_id:
        return Patient.objects.create(document_id=f"anon-{session_uuid[:8]}")

    extracted = {
        'full_name': patient_info.get('name'),
        'birth_date': _parse_iso_date(patient_info.get('birthDate')),
        'gender': patient_info.get('gender') if patient_info.get('gender') not in (None, 'unknown') else None,
        'phone': patient_info.get('phone'),
        'insurance': patient_info.get('insurance'),
    }
    patient, created = Patient.objects.select_for_update().get_or_create(
        document_id=document_id,
        defaults={
            'full_name': extracted['full_name'] or 'Paciente Sin Nombre',
            'birth_date': extracted['birth_date'],
            'gender': extracted['gender'] or 'unknown',
            'phone': extracted['phone'] or '',
            'insurance': extracted['insurance'] or 'Contributivo',
        }
    )
    if not created:
        placeholders = {'full_name': 'Paciente Sin Nombre', 'gender': 'unknown'}
        changed = []
        for field, value in extracted.items():
            current = getattr(patient, field)
            if value and (not current or current == placeholders.get(field)):
                setattr(patient, field, value)
                changed.append(field)
        if changed:
            patient.save(update_fields=changed)
    return patient


def _split_transcript(full_text: str) -> list:
    """Reconstruye los turnos 'Hablante: texto' que el frontend envia unidos por saltos de linea."""
    turns = []
    for line in (full_text or '').splitlines():
        if not line.strip():
            continue
        speaker, sep, text = line.partition(': ')
        turns.append({"speaker": speaker, "text": text} if sep else {"speaker": "Transcripcion", "text": line})
    return turns


def _level_matrix(queryset, evaluated_field: str, reference_field: str):
    """Matriz de confusion 5x5 calculada con un GROUP BY (como maximo 25 filas)."""
    rows = (queryset.order_by()
            .values_list(evaluated_field, reference_field)
            .annotate(n=Count('id')))
    return confusion_matrix_from_counts(rows)
