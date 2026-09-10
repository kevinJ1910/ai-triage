from rest_framework import serializers
from .models import SystemConfiguration, APIKeyCredential
from .crypto import detect_key_provider

class SystemConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemConfiguration
        fields = [
            'active_asr_model',
            'active_llm_engine',
            'active_ner_model',
            'snomed_version',
            'snomed_updated_at',
            'icd10_version',
            'icd10_updated_at',
            'updated_at',
        ]

class APIKeyCredentialSerializer(serializers.ModelSerializer):
    provider_display = serializers.CharField(source='get_provider_display', read_only=True)

    class Meta:
        model = APIKeyCredential
        fields = [
            'id',
            'provider',
            'provider_display',
            'name',
            'masked_key',
            'is_active',
            'created_at',
        ]

class CreateAPIKeySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    api_key = serializers.CharField(write_only=True, min_length=10)
    provider = serializers.CharField(max_length=30, required=False, allow_blank=True)

    def create(self, validated_data):
        raw_key = validated_data['api_key'].strip()
        provider = validated_data.get('provider')
        if not provider:
            provider = detect_key_provider(raw_key)

        credential = APIKeyCredential(
            name=validated_data['name'].strip(),
            provider=provider
        )
        credential.set_key(raw_key)
        credential.save()
        return credential
