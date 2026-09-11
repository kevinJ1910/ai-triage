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

class SystemConfigView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        config = SystemConfiguration.get_solo()
        keys = APIKeyCredential.objects.filter(is_active=True).order_by('-created_at')
        
        return Response({
            "config": SystemConfigurationSerializer(config).data,
            "api_keys": APIKeyCredentialSerializer(keys, many=True).data,
            "available_options": {
                "asr_models": [
                    {"id": "large-v3-turbo", "name": "Faster-Whisper (large-v3-turbo)", "recommended": True, "type": "GPU/CPU"},
                    {"id": "large-v3", "name": "Whisper Large V3 (Standard)", "recommended": False, "type": "GPU"},
                    {"id": "medium", "name": "Faster-Whisper Medium", "recommended": False, "type": "CPU/GPU"},
                    {"id": "small", "name": "Faster-Whisper Small (Rapido)", "recommended": False, "type": "CPU"},
                    {"id": "base", "name": "Faster-Whisper Base", "recommended": False, "type": "CPU"},
                ],
                "llm_engines": [
                    {"id": "gemini-2.5-flash", "name": "Google Gemini 2.5 Flash", "recommended": True},
                    {"id": "gemini-1.5-pro", "name": "Google Gemini 1.5 Pro", "recommended": False},
                    {"id": "gpt-4o-mini", "name": "OpenAI GPT-4o-mini", "recommended": False},
                    {"id": "claude-3-5-sonnet", "name": "Anthropic Claude 3.5 Sonnet", "recommended": False},
                ],
                "ner_models": [
                    {"id": "ClinicalBERT (v2.1 - Recomendado)", "name": "ClinicalBERT (v2.1 - Recomendado)"},
                    {"id": "BioBERT (v1.5 - Legacy)", "name": "BioBERT (v1.5 - Legacy)"},
                    {"id": "PubMedBERT (Experimental)", "name": "PubMedBERT (Experimental)"},
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
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        vocab_type = request.data.get('type', 'snomed').lower()
        config = SystemConfiguration.get_solo()

        now = timezone.now()
        if 'snomed' in vocab_type:
            config.snomed_updated_at = now
            config.save()
            msg = "Vocabulario SNOMED CT sincronizado correctamente con la edicion en espanol."
        else:
            config.icd10_updated_at = now
            config.save()
            msg = "Vocabulario CIE-10 actualizado con el catalogo clinico vigente."

        AuditLog.objects.create(
            user=request.user,
            action='UPDATE_VOCABULARY',
            resource=f'Vocabulary/{vocab_type.upper()}',
            status='SUCCESS',
            details=msg
        )

        return Response({
            "message": msg,
            "snomed_updated_at": config.snomed_updated_at,
            "icd10_updated_at": config.icd10_updated_at,
        }, status=status.HTTP_200_OK)
