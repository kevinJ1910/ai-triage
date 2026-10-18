"""
Módulo central de validación tipada y esquemas Pydantic para AI-Triage.
Asegura tipos estrictos en campos críticos (emails, numéricos, fechas, booleanos)
manteniendo flexibilidad en cargas dinámicas (JSON payloads, metadatos, bundles FHIR).
"""

from typing import Optional, List, Dict, Any, Union, Literal
from datetime import date
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator, ValidationError
from rest_framework.response import Response
from rest_framework import status
from rest_framework import serializers

# ==========================================
# UTILIDADES DE VALIDACIÓN
# ==========================================

def validate_payload(schema_cls: type[BaseModel], data: Any):
    """
    Valida un diccionario o carga recibida contra un esquema Pydantic.
    Retorna la instancia validada en caso de éxito.
    Lanza rest_framework.serializers.ValidationError formateada en caso de error.
    """
    try:
        return schema_cls.model_validate(data)
    except ValidationError as e:
        field_errors = {}
        for err in e.errors():
            loc_parts = [str(x) for x in err['loc'] if x != '__root__']
            field_name = loc_parts[-1] if loc_parts else 'non_field_errors'
            msg = err['msg']
            if field_name in field_errors:
                if isinstance(field_errors[field_name], list):
                    field_errors[field_name].append(msg)
                else:
                    field_errors[field_name] = [field_errors[field_name], msg]
            else:
                field_errors[field_name] = [msg]
        raise serializers.ValidationError(field_errors)

# ==========================================
# ESQUEMAS: CUENTAS Y AUTENTICACIÓN
# ==========================================

class LoginSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, description="Contraseña obligatoria")

class RegisterSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    confirm_password: str = Field(min_length=6)
    first_name: Optional[str] = Field(default="", max_length=150)
    last_name: Optional[str] = Field(default="", max_length=150)
    document_id: Optional[str] = Field(default=None, max_length=50)
    phone: Optional[str] = Field(default="", max_length=30)  # Flexible
    role: Optional[Literal['medico', 'enfermero', 'admin']] = 'medico'

    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v, info):
        if 'password' in info.data and v != info.data['password']:
            raise ValueError('Las contrasenas no coinciden')
        return v

class VerifyCodeSchema(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r'^\d{6}$')

class ResendCodeSchema(BaseModel):
    email: EmailStr

class PasswordResetRequestSchema(BaseModel):
    email: EmailStr

class PasswordResetConfirmSchema(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r'^\d{6}$')
    new_password: str = Field(min_length=6)
    confirm_password: str = Field(min_length=6)

    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v, info):
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Las contraseñas no coinciden')
        return v

class UserPermissionUpdateSchema(BaseModel):
    can_use_transcriber: Optional[bool] = None
    can_edit_symptoms: Optional[bool] = None
    can_register_patients: Optional[bool] = None
    can_view_emr: Optional[bool] = None
    can_view_fhir: Optional[bool] = None
    can_manage_config: Optional[bool] = None

# ==========================================
# ESQUEMAS: PACIENTES
# ==========================================

class PatientCreateSchema(BaseModel):
    document_id: str = Field(min_length=3, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    birth_date: Optional[Union[date, str]] = None
    gender: Optional[str] = Field(default='unknown', max_length=20)
    insurance: Optional[str] = Field(default='Contributivo', max_length=100)
    phone: Optional[str] = Field(default='', max_length=30)
    contact_info: Optional[Dict[str, Any]] = None  # Flexible

# ==========================================
# ESQUEMAS: TRIAJE Y CLÍNICA
# ==========================================

class TriageOverrideSchema(BaseModel):
    final_level: Optional[int] = Field(default=None, ge=1, le=5, description="Nivel de triaje del 1 al 5")
    override_reason: Optional[str] = Field(default="", max_length=1000)
    justification: Optional[str] = Field(default=None, max_length=5000)
    final_symptoms: Optional[List[str]] = None  # Flexible

class TriageReferenceSchema(BaseModel):
    reference_level: int = Field(ge=1, le=5, description="Nivel de referencia asignado a ciegas (1-5)")

class EMRBoxAssignSchema(BaseModel):
    assigned_box: Optional[str] = Field(default=None, max_length=50)
    box_name: Optional[str] = Field(default=None, max_length=50)
    status: Optional[str] = Field(default="En Atencion", max_length=50)

    @model_validator(mode='after')
    def validate_box_presence(self):
        resolved = self.assigned_box or self.box_name
        if not resolved or not resolved.strip():
            raise ValueError("assigned_box o box_name debe ser proporcionado y no vacio")
        self.assigned_box = resolved.strip()
        return self


class FHIRSyncSchema(BaseModel):
    resourceType: Literal['Bundle']
    type: str = Field(min_length=1)
    timestamp: Optional[str] = None
    entry: Optional[List[Dict[str, Any]]] = None  # Carga FHIR flexible

# ==========================================
# ESQUEMAS: CONFIGURACIÓN Y LLAVES API
# ==========================================

class SystemConfigUpdateSchema(BaseModel):
    model_config = {"extra": "forbid"}
    active_asr_model: Optional[str] = None
    active_llm_engine: Optional[str] = None
    active_ner_model: Optional[str] = None
    snomed_version: Optional[str] = None
    icd10_version: Optional[str] = None

class APIKeyCreateSchema(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider: Optional[Literal['gemini', 'custom']] = None
    api_key: str = Field(min_length=4, max_length=500)
    description: Optional[str] = Field(default="", max_length=500)

    @field_validator('provider', mode='before')
    @classmethod
    def normalize_provider(cls, v):
        if v == "" or (isinstance(v, str) and not v.strip()) or v is None:
            return None
        return v

# ==========================================
# ESQUEMAS: TRANSCRIPCIÓN Y NORMALIZACIÓN
# ==========================================

class NormalizeTextSchema(BaseModel):
    raw_text: str = Field(min_length=1, max_length=10000)
