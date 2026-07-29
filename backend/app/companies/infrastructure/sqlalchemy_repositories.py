from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.companies.domain.entities import (
    AuditorAccessRequest,
    AuditorAccessRequestStatus,
    AuditorSession,
    Company,
    CompanyDeviceLink,
    CompanyDeviceLinkStatus,
    CompanyStatus,
    EnrollmentCode,
    EnrollmentRequest,
    EnrollmentRequestStatus,
)
from backend.app.companies.infrastructure.sqlalchemy_models import (
    AuditorAccessRequestModel,
    AuditorSessionModel,
    CompanyDeviceLinkModel,
    CompanyModel,
    EnrollmentCodeModel,
    EnrollmentRequestModel,
)


def _company_to_domain(model: CompanyModel) -> Company:
    return Company(
        company_id=model.company_id,
        name=model.name,
        phone_number=model.phone_number,
        created_at=model.created_at,
        status=CompanyStatus(model.status),
    )


def _update_company_model(model: CompanyModel, company: Company) -> None:
    model.name = company.name
    model.phone_number = company.phone_number
    model.created_at = company.created_at
    model.status = company.status.value


def _enrollment_code_to_domain(model: EnrollmentCodeModel) -> EnrollmentCode:
    return EnrollmentCode(
        enrollment_code_id=model.enrollment_code_id,
        company_id=model.company_id,
        code_digest=model.code_digest,
        code_hash=model.code_hash,
        code_salt=model.code_salt,
        created_at=model.created_at,
        expires_at=model.expires_at,
        max_uses=model.max_uses,
        used_count=model.used_count,
        revoked_at=model.revoked_at,
    )


def _update_enrollment_code_model(
    model: EnrollmentCodeModel,
    enrollment_code: EnrollmentCode,
) -> None:
    model.company_id = enrollment_code.company_id
    model.code_digest = enrollment_code.code_digest
    model.code_hash = enrollment_code.code_hash
    model.code_salt = enrollment_code.code_salt
    model.created_at = enrollment_code.created_at
    model.expires_at = enrollment_code.expires_at
    model.max_uses = enrollment_code.max_uses
    model.used_count = enrollment_code.used_count
    model.revoked_at = enrollment_code.revoked_at


def _enrollment_request_to_domain(model: EnrollmentRequestModel) -> EnrollmentRequest:
    snapshot = cast(dict[str, str], model.device_fingerprint_snapshot or {})
    return EnrollmentRequest(
        enrollment_request_id=model.enrollment_request_id,
        company_id=model.company_id,
        device_id=model.device_id,
        requested_at=model.requested_at,
        status=EnrollmentRequestStatus(model.status),
        reviewed_by_auditor_session_id=model.reviewed_by_auditor_session_id,
        reviewed_at=model.reviewed_at,
        device_fingerprint_snapshot=dict(snapshot),
    )


def _update_enrollment_request_model(
    model: EnrollmentRequestModel,
    enrollment_request: EnrollmentRequest,
) -> None:
    model.company_id = enrollment_request.company_id
    model.device_id = enrollment_request.device_id
    model.requested_at = enrollment_request.requested_at
    model.status = enrollment_request.status.value
    model.reviewed_by_auditor_session_id = enrollment_request.reviewed_by_auditor_session_id
    model.reviewed_at = enrollment_request.reviewed_at
    model.device_fingerprint_snapshot = dict(enrollment_request.device_fingerprint_snapshot)


def _company_device_link_to_domain(model: CompanyDeviceLinkModel) -> CompanyDeviceLink:
    return CompanyDeviceLink(
        company_device_link_id=model.company_device_link_id,
        company_id=model.company_id,
        device_id=model.device_id,
        linked_at=model.linked_at,
        status=CompanyDeviceLinkStatus(model.status),
        revoked_at=model.revoked_at,
        revoked_by_device=model.revoked_by_device,
        revoked_by_auditor_session_id=model.revoked_by_auditor_session_id,
    )


def _update_company_device_link_model(
    model: CompanyDeviceLinkModel,
    link: CompanyDeviceLink,
) -> None:
    model.company_id = link.company_id
    model.device_id = link.device_id
    model.linked_at = link.linked_at
    model.status = link.status.value
    model.revoked_at = link.revoked_at
    model.revoked_by_device = link.revoked_by_device
    model.revoked_by_auditor_session_id = link.revoked_by_auditor_session_id


def _auditor_access_request_to_domain(
    model: AuditorAccessRequestModel,
) -> AuditorAccessRequest:
    return AuditorAccessRequest(
        auditor_access_request_id=model.auditor_access_request_id,
        company_id=model.company_id,
        device_id=model.device_id,
        otp_hash=model.otp_hash,
        otp_salt=model.otp_salt,
        requested_at=model.requested_at,
        expires_at=model.expires_at,
        status=AuditorAccessRequestStatus(model.status),
        verified_at=model.verified_at,
        auditor_session_id=model.auditor_session_id,
        failed_attempts=model.failed_attempts,
    )


def _update_auditor_access_request_model(
    model: AuditorAccessRequestModel,
    access_request: AuditorAccessRequest,
) -> None:
    model.company_id = access_request.company_id
    model.device_id = access_request.device_id
    model.otp_hash = access_request.otp_hash
    model.otp_salt = access_request.otp_salt
    model.requested_at = access_request.requested_at
    model.expires_at = access_request.expires_at
    model.status = access_request.status.value
    model.verified_at = access_request.verified_at
    model.auditor_session_id = access_request.auditor_session_id
    model.failed_attempts = access_request.failed_attempts


def _auditor_session_to_domain(model: AuditorSessionModel) -> AuditorSession:
    scopes = cast(list[str], model.scopes or [])
    return AuditorSession(
        auditor_session_id=model.auditor_session_id,
        company_id=model.company_id,
        device_id=model.device_id,
        created_at=model.created_at,
        expires_at=model.expires_at,
        scopes=tuple(scopes),
        revoked_at=model.revoked_at,
    )


def _update_auditor_session_model(model: AuditorSessionModel, session: AuditorSession) -> None:
    model.company_id = session.company_id
    model.device_id = session.device_id
    model.created_at = session.created_at
    model.expires_at = session.expires_at
    model.scopes = list(session.scopes)
    model.revoked_at = session.revoked_at


class SQLAlchemyCompanyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, company: Company) -> Company:
        model = self._session.get(CompanyModel, company.company_id)
        if model is None:
            model = CompanyModel(
                company_id=company.company_id,
                name=company.name,
                phone_number=company.phone_number,
                created_at=company.created_at,
                status=company.status.value,
            )
            self._session.add(model)
        else:
            _update_company_model(model, company)
        self._session.flush()
        return _company_to_domain(model)

    def find_by_id(self, company_id: str) -> Company | None:
        model = self._session.get(CompanyModel, company_id)
        return _company_to_domain(model) if model is not None else None

    def list_all(self) -> list[Company]:
        statement = select(CompanyModel).order_by(CompanyModel.created_at.desc())
        return [_company_to_domain(model) for model in self._session.scalars(statement).all()]


class SQLAlchemyEnrollmentCodeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, enrollment_code: EnrollmentCode) -> EnrollmentCode:
        model = self._session.get(EnrollmentCodeModel, enrollment_code.enrollment_code_id)
        if model is None:
            model = EnrollmentCodeModel(
                enrollment_code_id=enrollment_code.enrollment_code_id,
                company_id=enrollment_code.company_id,
                code_digest=enrollment_code.code_digest,
                code_hash=enrollment_code.code_hash,
                code_salt=enrollment_code.code_salt,
                created_at=enrollment_code.created_at,
                expires_at=enrollment_code.expires_at,
                max_uses=enrollment_code.max_uses,
                used_count=enrollment_code.used_count,
                revoked_at=enrollment_code.revoked_at,
            )
            self._session.add(model)
        else:
            _update_enrollment_code_model(model, enrollment_code)
        self._session.flush()
        return _enrollment_code_to_domain(model)

    def find_by_id(self, enrollment_code_id: str) -> EnrollmentCode | None:
        model = self._session.get(EnrollmentCodeModel, enrollment_code_id)
        return _enrollment_code_to_domain(model) if model is not None else None

    def find_by_code_digest(self, code_digest: str) -> EnrollmentCode | None:
        statement = select(EnrollmentCodeModel).where(
            EnrollmentCodeModel.code_digest == code_digest,
        ).with_for_update()
        model = self._session.scalars(statement).first()
        return _enrollment_code_to_domain(model) if model is not None else None


class SQLAlchemyEnrollmentRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, enrollment_request: EnrollmentRequest) -> EnrollmentRequest:
        model = self._session.get(
            EnrollmentRequestModel,
            enrollment_request.enrollment_request_id,
        )
        if model is None:
            model = EnrollmentRequestModel(
                enrollment_request_id=enrollment_request.enrollment_request_id,
                company_id=enrollment_request.company_id,
                device_id=enrollment_request.device_id,
                requested_at=enrollment_request.requested_at,
                status=enrollment_request.status.value,
                reviewed_by_auditor_session_id=(
                    enrollment_request.reviewed_by_auditor_session_id
                ),
                reviewed_at=enrollment_request.reviewed_at,
                device_fingerprint_snapshot=dict(
                    enrollment_request.device_fingerprint_snapshot,
                ),
            )
            self._session.add(model)
        else:
            _update_enrollment_request_model(model, enrollment_request)
        self._session.flush()
        return _enrollment_request_to_domain(model)

    def find_by_id(self, enrollment_request_id: str) -> EnrollmentRequest | None:
        model = self._session.get(EnrollmentRequestModel, enrollment_request_id)
        return _enrollment_request_to_domain(model) if model is not None else None

    def find_pending_by_company_and_device(
        self,
        *,
        company_id: str,
        device_id: str,
    ) -> EnrollmentRequest | None:
        statement = select(EnrollmentRequestModel).where(
            EnrollmentRequestModel.company_id == company_id,
            EnrollmentRequestModel.device_id == device_id,
            EnrollmentRequestModel.status == "PENDING",
        )
        model = self._session.scalars(statement).first()
        return _enrollment_request_to_domain(model) if model is not None else None

    def list_by_company(
        self,
        *,
        company_id: str,
        status: str | None = None,
    ) -> list[EnrollmentRequest]:
        statement = select(EnrollmentRequestModel).where(
            EnrollmentRequestModel.company_id == company_id,
        )
        if status:
            statement = statement.where(EnrollmentRequestModel.status == status)
        statement = statement.order_by(EnrollmentRequestModel.requested_at.desc())
        return [
            _enrollment_request_to_domain(model)
            for model in self._session.scalars(statement).all()
        ]


class SQLAlchemyCompanyDeviceLinkRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, link: CompanyDeviceLink) -> CompanyDeviceLink:
        model = self._session.get(CompanyDeviceLinkModel, link.company_device_link_id)
        if model is None:
            model = CompanyDeviceLinkModel(
                company_device_link_id=link.company_device_link_id,
                company_id=link.company_id,
                device_id=link.device_id,
                linked_at=link.linked_at,
                status=link.status.value,
                revoked_at=link.revoked_at,
                revoked_by_device=link.revoked_by_device,
                revoked_by_auditor_session_id=link.revoked_by_auditor_session_id,
            )
            self._session.add(model)
        else:
            _update_company_device_link_model(model, link)
        self._session.flush()
        return _company_device_link_to_domain(model)

    def find_by_id(self, company_device_link_id: str) -> CompanyDeviceLink | None:
        model = self._session.get(CompanyDeviceLinkModel, company_device_link_id)
        return _company_device_link_to_domain(model) if model is not None else None

    def find_active_by_company_and_device(
        self,
        *,
        company_id: str,
        device_id: str,
    ) -> CompanyDeviceLink | None:
        statement = select(CompanyDeviceLinkModel).where(
            CompanyDeviceLinkModel.company_id == company_id,
            CompanyDeviceLinkModel.device_id == device_id,
            CompanyDeviceLinkModel.status == "ACTIVE",
            CompanyDeviceLinkModel.revoked_at.is_(None),
        )
        model = self._session.scalars(statement).first()
        return _company_device_link_to_domain(model) if model is not None else None

    def list_by_company(self, company_id: str) -> list[CompanyDeviceLink]:
        statement = (
            select(CompanyDeviceLinkModel)
            .where(CompanyDeviceLinkModel.company_id == company_id)
            .order_by(CompanyDeviceLinkModel.linked_at.desc())
        )
        return [
            _company_device_link_to_domain(model)
            for model in self._session.scalars(statement).all()
        ]

    def list_by_device(self, device_id: str) -> list[CompanyDeviceLink]:
        statement = (
            select(CompanyDeviceLinkModel)
            .where(CompanyDeviceLinkModel.device_id == device_id)
            .order_by(CompanyDeviceLinkModel.linked_at.desc())
        )
        return [
            _company_device_link_to_domain(model)
            for model in self._session.scalars(statement).all()
        ]


class SQLAlchemyAuditorAccessRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, access_request: AuditorAccessRequest) -> AuditorAccessRequest:
        model = self._session.get(
            AuditorAccessRequestModel,
            access_request.auditor_access_request_id,
        )
        if model is None:
            model = AuditorAccessRequestModel(
                auditor_access_request_id=access_request.auditor_access_request_id,
                company_id=access_request.company_id,
                device_id=access_request.device_id,
                otp_hash=access_request.otp_hash,
                otp_salt=access_request.otp_salt,
                requested_at=access_request.requested_at,
                expires_at=access_request.expires_at,
                status=access_request.status.value,
                verified_at=access_request.verified_at,
                auditor_session_id=access_request.auditor_session_id,
                failed_attempts=access_request.failed_attempts,
            )
            self._session.add(model)
        else:
            _update_auditor_access_request_model(model, access_request)
        self._session.flush()
        return _auditor_access_request_to_domain(model)

    def find_by_id(self, auditor_access_request_id: str) -> AuditorAccessRequest | None:
        model = self._session.get(AuditorAccessRequestModel, auditor_access_request_id)
        return _auditor_access_request_to_domain(model) if model is not None else None


class SQLAlchemyAuditorSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, session: AuditorSession) -> AuditorSession:
        model = self._session.get(AuditorSessionModel, session.auditor_session_id)
        if model is None:
            model = AuditorSessionModel(
                auditor_session_id=session.auditor_session_id,
                company_id=session.company_id,
                device_id=session.device_id,
                created_at=session.created_at,
                expires_at=session.expires_at,
                scopes=list(session.scopes),
                revoked_at=session.revoked_at,
            )
            self._session.add(model)
        else:
            _update_auditor_session_model(model, session)
        self._session.flush()
        return _auditor_session_to_domain(model)

    def find_by_id(self, auditor_session_id: str) -> AuditorSession | None:
        model = self._session.get(AuditorSessionModel, auditor_session_id)
        return _auditor_session_to_domain(model) if model is not None else None

    def list_active_by_company(self, company_id: str) -> list[AuditorSession]:
        statement = select(AuditorSessionModel).where(
            AuditorSessionModel.company_id == company_id,
            AuditorSessionModel.revoked_at.is_(None),
        )
        return [
            _auditor_session_to_domain(model)
            for model in self._session.scalars(statement).all()
        ]
