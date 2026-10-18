from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from .models import SystemConfiguration, APIKeyCredential
from .serializers import (
    SystemConfigurationSerializer,
    APIKeyCredentialSerializer,
    CreateAPIKeySerializer
)
from accounts.models import AuditLog


class EngineStatusView(APIView):
    """Estado de los motores de inferencia (ASR, NER y LLM) para el personal autenticado."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        import os
        from transcription.tasks import get_asr_status, worker_mode
        from triage.ner_model import get_ner_status
        from triage.ai_analyzer import _resolve_gemini_api_key

        asr = get_asr_status(load=False)
        ner = get_ner_status()
        config = SystemConfiguration.get_solo()
        return Response({
            "inference_mode": "worker" if worker_mode() else "inline",
            "asr": {
                "model_loaded": bool(asr.get("model_loaded")),
                "model_size": asr.get("model_size"),
                "device": asr.get("device"),
                "compute_type": asr.get("compute_type"),
            },
            "ner": {
                "model_loaded": bool(ner.get("model_loaded")),
                "mode": config.active_ner_model,
                # Nombre de la carpeta del modelo; se lee del estado publicado sin cargar el modelo aqui.
                "engine": os.path.basename(str(ner.get("source") or "").rstrip("/")) or None,
                "detail": ner.get("detail", ""),
            },
            # Nunca se devuelve la clave: solo si hay una configurada.
            "llm": {"configured": bool(_resolve_gemini_api_key()), "model": config.active_llm_engine},
        })

TOKEN_NOTICE = (
    "Las capas del catalogo (correcciones ASR, abreviaturas y coloquialismos) no consumen tokens. "
    "Gemini Flash-Lite solo se usa en el monitor de normalizacion para los terminos que el catalogo no resolvio; "
    "el triaje no hace una segunda llamada para normalizar."
)


def _vocabularies(config, catalog):
    """Estado real de los vocabularios locales (transcription/terminology), no cifras de catalogos externos."""
    snomed, cie10 = catalog['snomed'], catalog['cie10']
    return {
        "snomed": {
            "code": "snomed_ct",
            "title": snomed['edicion'],
            "provider": "SNOMED International; cada codigo verificado con tx.fhir.org (HL7)",
            "updated_at": config.snomed_updated_at,
            "total_terms": snomed['codigos'],
            "indexed_emergency_terms": catalog['conceptos_con_snomed'],
            "status": "COMPLETO" if snomed['completo'] else "SUBCONJUNTO VERIFICADO",
            "update_available": False,
            "latest_release": snomed['version'],
            "token_notice": TOKEN_NOTICE,
        },
        "icd10": {
            "code": "cie10_oms",
            "title": "CIE-10 (OMS)",
            "provider": cie10['fuente'],
            "updated_at": config.icd10_updated_at,
            "total_terms": cie10['codigos'],
            "indexed_emergency_terms": catalog['conceptos_con_cie10'],
            "status": "COMPLETO" if cie10['completo'] else "SUBCONJUNTO",
            "update_available": False,
            "latest_release": cie10['version'],
            "token_notice": TOKEN_NOTICE,
        },
    }


class SystemConfigView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .services import sync_environment_api_keys
        sync_environment_api_keys()

        config = SystemConfiguration.get_solo()
        keys = APIKeyCredential.objects.filter(is_active=True).order_by('-created_at')
        
        # Dispositivo real del motor ASR: lo publica worker-asr (o el proceso web en modo en linea).
        import os
        from transcription.tasks import get_asr_status
        try:
            asr_status = get_asr_status(load=False)
        except Exception:
            asr_status = {"device": "unknown"}
        asr_device = asr_status.get("device")
        cuda_available = asr_device == "cuda"
        if cuda_available:
            device_info = "GPU CUDA (NVIDIA)"
        elif asr_device == "cpu":
            device_info = f"CPU ({asr_status.get('compute_type', 'int8').upper()})"
        else:
            device_info = "ASR sin iniciar"
        has_gemini = bool(os.environ.get("GEMINI_API_KEY") or keys.filter(provider='gemini').exists())
        from triage.ner_model import get_ner_status
        from transcription.terminology import catalog_summary
        catalog = catalog_summary()

        return Response({
            "config": SystemConfigurationSerializer(config).data,
            "api_keys": APIKeyCredentialSerializer(keys, many=True).data,
            "runtime_status": {
                "cuda_available": cuda_available,
                "hardware_device": device_info,
                "asr_model_in_use": asr_status.get("model_size"),
                "gemini_configured": has_gemini,
                "active_keys_count": keys.count(),
                "system_timezone": str(timezone.get_current_timezone()),
                "ner_status": get_ner_status(),
            },
            "vocabularies": _vocabularies(config, catalog),
            "catalog": catalog,
            "available_options": {
                "asr_models": [
                    {"id": "auto", "name": "Segun entorno (WHISPER_MODEL_SIZE)", "recommended": True, "type": "CPU/GPU", "description": "small en CPU, large-v3-turbo con GPU NVIDIA"},
                    {"id": "large-v3-turbo", "name": "Faster-Whisper (large-v3-turbo)", "recommended": False, "type": "GPU/CPU", "description": "Alta precision clinica optimizada"},
                    {"id": "large-v3", "name": "Whisper Large V3 (Standard)", "recommended": False, "type": "GPU", "description": "Modelo de referencia OpenAI"},
                    {"id": "medium", "name": "Faster-Whisper Medium", "recommended": False, "type": "CPU/GPU", "description": "Balance velocidad/precision"},
                    {"id": "small", "name": "Faster-Whisper Small", "recommended": False, "type": "CPU", "description": "Baja latencia en equipos livianos"},
                    {"id": "base", "name": "Faster-Whisper Base", "recommended": False, "type": "CPU", "description": "Ahorro extremo de memoria"},
                    {"id": "tiny", "name": "Faster-Whisper Tiny", "recommended": False, "type": "CPU", "description": "Ultra rapido para pruebas basicas"},
                ],
                "llm_engines": [
                    {"id": "gemini-2.5-flash", "name": "Google Gemini 2.5 Flash", "recommended": True, "provider": "Google Gemini", "description": "Baja latencia y alta precision clinica"},
                    {"id": "gemini-3.5-flash-lite", "name": "Google Gemini 3.5 Flash-Lite", "recommended": False, "provider": "Google Gemini", "description": "Generacion actual, bajo costo"},
                    {"id": "gemini-3.8-flash", "name": "Google Gemini 3.8 Flash", "recommended": False, "provider": "Google Gemini", "description": "Generacion actual, balance precision/latencia"},
                ],
                "ner_models": [
                    {"id": "auto", "name": "RoBERTa clinico + catalogo", "recommended": True,
                     "description": "PlanTL-GOB-ES/roberta-base-biomedical-clinical-es ajustado (ml/ner); sin modelo cargado se usa el catalogo"},
                    {"id": "catalogo", "name": "Solo catalogo terminologico y LLM", "recommended": False,
                     "description": "Desactiva RoBERTa: entidades del catalogo y de Gemini"},
                ]
            }
        })

    def post(self, request):
        if not (request.user.role == 'admin' or request.user.is_superuser or getattr(request.user.permissions, 'can_manage_config', False)):
            return Response({"detail": "Permiso denegado. Solo administradores pueden modificar la configuracion global."}, status=status.HTTP_403_FORBIDDEN)

        from core.validation import validate_payload, SystemConfigUpdateSchema
        try:
            validate_payload(SystemConfigUpdateSchema, request.data)
        except Exception as e:
            return Response(getattr(e, 'detail', {"detail": str(e)}), status=status.HTTP_400_BAD_REQUEST)

        config = SystemConfiguration.get_solo()
        serializer = SystemConfigurationSerializer(config, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()

            AuditLog.objects.create(
                user=request.user,
                action='MODEL_CONFIG_CHANGE',
                resource='SystemConfiguration',
                status='SUCCESS',
                details=f"Modelos actualizados: {request.data}"
            )

            return Response({
                "message": "Configuracion guardada exitosamente.",
                "config": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class APIKeyListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from .services import sync_environment_api_keys
        sync_environment_api_keys()

        keys = APIKeyCredential.objects.filter(is_active=True).order_by('-created_at')
        return Response(APIKeyCredentialSerializer(keys, many=True).data)

    def post(self, request):
        if not (request.user.role == 'admin' or request.user.is_superuser or getattr(request.user.permissions, 'can_manage_config', False)):
            return Response({"detail": "Solo administradores pueden registrar llaves API cifradas."}, status=status.HTTP_403_FORBIDDEN)

        from core.validation import validate_payload, APIKeyCreateSchema
        try:
            validated = validate_payload(APIKeyCreateSchema, request.data)
        except Exception as e:
            return Response(getattr(e, 'detail', {"detail": str(e)}), status=status.HTTP_400_BAD_REQUEST)

        serializer = CreateAPIKeySerializer(data=validated.model_dump())
        if serializer.is_valid():
            credential = serializer.save()

            AuditLog.objects.create(
                user=request.user,
                action='API_KEY_ADDED',
                resource=f'APIKeyCredential/{credential.id}',
                status='SUCCESS',
                details=f"Nueva llave registrada: {credential.name} ({credential.provider})"
            )

            return Response({
                "message": "Llave API cifrada y almacenada de forma segura.",
                "credential": APIKeyCredentialSerializer(credential).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class APIKeyDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, key_id):
        if not (request.user.role == 'admin' or request.user.is_superuser or getattr(request.user.permissions, 'can_manage_config', False)):
            return Response({"detail": "Permiso denegado."}, status=status.HTTP_403_FORBIDDEN)

        try:
            credential = APIKeyCredential.objects.get(id=key_id)
        except APIKeyCredential.DoesNotExist:
            return Response({"detail": "Llave no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        key_name = credential.name
        credential.delete()

        AuditLog.objects.create(
            user=request.user,
            action='API_KEY_DELETED',
            resource=f'APIKeyCredential/{key_id}',
            status='SUCCESS',
            details=f"Llave eliminada: {key_name}"
        )

        return Response({"message": f"Llave '{key_name}' eliminada correctamente."}, status=status.HTTP_200_OK)

class VocabularySyncView(APIView):
    """
    'check_update' valida los catalogos locales; 'sync' los recarga en memoria (tras editarlos o importar la
    tabla CIE-10) y los valida. La verificacion de SNOMED CT contra el servidor terminologico es un comando
    aparte (python manage.py verify_snomed), porque consulta cientos de codigos.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not (request.user.role == 'admin' or request.user.is_superuser or getattr(request.user.permissions, 'can_manage_config', False)):
            return Response({"detail": "Permiso denegado. Solo administradores pueden sincronizar vocabularios."}, status=status.HTTP_403_FORBIDDEN)

        from transcription.terminology import catalog_summary, clear_caches

        vocab_type = str(request.data.get('type', 'snomed')).lower()
        action = request.data.get('action', 'sync')
        is_snomed = 'snomed' in vocab_type
        config = SystemConfiguration.get_solo()

        if action != 'check_update':
            clear_caches()
        catalog = catalog_summary()
        vocab = _vocabularies(config, catalog)['snomed' if is_snomed else 'icd10']
        errors = catalog['errores']
        if errors:
            message = f"El catalogo tiene {len(errors)} errores de consistencia: {errors[0]}"
        elif is_snomed:
            message = (f"{vocab['total_terms']} codigos SNOMED CT verificados ({vocab['title']}) en "
                       f"{vocab['indexed_emergency_terms']} conceptos del catalogo. Para volver a verificarlos "
                       "contra el servidor: python manage.py verify_snomed")
        else:
            message = (f"{vocab['total_terms']} codigos CIE-10 en el catalogo local ({vocab['status'].lower()}), "
                       f"usados por {vocab['indexed_emergency_terms']} conceptos.")

        if action == 'check_update':
            return Response({"action": "check_update", "vocab_type": vocab_type, **vocab, "errors": errors,
                             "message": message}, status=status.HTTP_200_OK)

        now = timezone.now()
        if is_snomed:
            config.snomed_updated_at = now
        else:
            config.icd10_updated_at = now
        config.save()
        AuditLog.objects.create(
            user=request.user,
            action='UPDATE_VOCABULARY',
            resource=f'Vocabulary/{vocab_type.upper()}',
            status='SUCCESS' if not errors else 'FAILURE',
            details=message,
        )
        return Response({
            "message": f"Catalogo recargado. {message}",
            "vocab_type": vocab_type,
            "total_terms": vocab['total_terms'],
            "indexed_emergency_terms": vocab['indexed_emergency_terms'],
            "errors": errors,
            "snomed_updated_at": config.snomed_updated_at,
            "icd10_updated_at": config.icd10_updated_at,
            "token_notice": TOKEN_NOTICE,
        }, status=status.HTTP_200_OK)
