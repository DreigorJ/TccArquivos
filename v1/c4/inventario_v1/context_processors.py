from typing import Dict

from .models import PerfilUsuario


def can_manage_users(request) -> Dict[str, bool]:
    """
    Context processor que adiciona a flag `can_manage_users` em todos os templates.
    True somente quando o usuário autenticado possui perfil com papel 'administrador'.
    """
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"can_manage_users": False}

    try:
        perfil = getattr(user, "perfil", None)
        if perfil and getattr(perfil, "papel", None) == PerfilUsuario.ROLE_ADMINISTRADOR:
            return {"can_manage_users": True}
    except Exception:
        # qualquer erro, considerar sem permissão
        pass
    return {"can_manage_users": False}