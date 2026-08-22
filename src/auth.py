import hmac
import streamlit as st
from pathlib import Path

def login_required() -> bool:
    if st.session_state.get("authenticated"):
        return True

    root = Path(__file__).resolve().parents[1]
    logo_candidates = [
        root / "assets" / "logo.png",
        root / "assets" / "logo.webp",
        root / "assets" / "logo.jpg",
        root / "assets" / "logo.svg",
    ]
    logo = next((p for p in logo_candidates if p.exists()), None)

    st.markdown("<div style='max-width:560px;margin:7vh auto 0 auto;text-align:center;'>", unsafe_allow_html=True)
    if logo:
        st.image(str(logo), width=300)
    st.markdown("""
      <div style="font-size:12px;letter-spacing:.16em;color:#6b7280;font-weight:700;margin-top:1rem">PRÉ-VIABILIDADE URBANÍSTICA</div>
      <div style="font-size:34px;font-weight:800;margin:.3rem 0 .4rem">Acesso reservado</div>
      <div style="color:#6b7280">Versão 4.2 Plus</div>
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    with st.form("login_form"):
        user = st.text_input("Utilizador")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Entrar", use_container_width=True)

    if submitted:
        auth_cfg = st.secrets.get("auth", {})
        expected_user = auth_cfg.get("username", "")
        expected_password = auth_cfg.get("password", "")
        if not expected_user or not expected_password:
            st.error("Autenticação não configurada. Define as credenciais nos Secrets privados do Streamlit.")
            return False
        ok = hmac.compare_digest(user, expected_user) and hmac.compare_digest(password, expected_password)
        if ok:
            st.session_state.authenticated = True
            st.rerun()
        st.error("Credenciais inválidas.")
    return False

def logout_button():
    if st.sidebar.button("Terminar sessão", use_container_width=True):
        st.session_state.clear()
        st.rerun()
