from contextvars import ContextVar
actor=ContextVar('site_actor',default=None)

def is_team():
    user=actor.get()
    return bool(user and user.is_authenticated and user.is_active and (user.is_superuser or user.role in ('TEACHER','STUDENT','ADMIN')))
