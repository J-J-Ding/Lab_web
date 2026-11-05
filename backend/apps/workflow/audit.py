from .models import BusinessAuditLog


def record(actor, target, action, fields=(), revision=None):
    """Store field names only, never private field values or request bodies."""
    return BusinessAuditLog.objects.create(actor=actor, actor_snapshot=actor.pk,
        target_id=target.pk, revision_id=revision.pk if revision else None,
        action=action, changed_fields=sorted(fields))
