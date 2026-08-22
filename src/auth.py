import hmac
from pathlib import Path
import streamlit as st
from src.ui import brand_logo

def login_required() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.markdown("<div style='height:4vh'></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1.2, 1, 1.2])
    with c2:
        brand_logo(login=True)
        st.markdown("""
        <div style="text-align:center;margin:18px 0 24px">
          <div style="font-size:11px;letter-spacing:.18em;color:#697386;font-weight:800">
            PRÉ-VIABILIDADE URBANÍSTICA
          </div>
          <div style="font-size:32px;line-height:1.08;font-weight:760;color:#171D2A;margin:10px 0 6px">
            Acesso reservado
          </div>
          <div style="font-size:13px;color:#8A93A3">doisarquitetos</div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            user = st.text_input(
                "Utilizador",
                value="",
                key="access_identifier_v42plus",
                placeholder=""
            )
            password = st.text_input(
                "Palavra-passe",
                value="",
                type="password",
                key="access_secret_v42plus",
                placeholder=""
            )
            submitted = st.form_submit_button("Entrar", use_container_width=True, type="primary")

        if submitted:
            auth_cfg = st.secrets.get("auth", {})
            expected_user = auth_cfg.get("username", "")
            expected_password = auth_cfg.get("password", "")
            if not expected_user or not expected_password:
                st.error("A autenticação ainda não está configurada nos Secrets privados.")
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
