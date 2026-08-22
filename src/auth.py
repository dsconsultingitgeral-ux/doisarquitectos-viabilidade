import hmac
import streamlit as st

def login_required() -> bool:
    if st.session_state.get("authenticated"):
        return True

    st.markdown("""
    <div style="max-width:560px;margin:8vh auto 1rem auto;">
      <div style="font-size:12px;letter-spacing:.16em;color:#6b7280;font-weight:700">DOISARQUITETOS</div>
      <div style="font-size:34px;font-weight:800;margin:.3rem 0 .4rem">Pré-Viabilidade Urbanística</div>
      <div style="color:#6b7280">Acesso reservado · versão V4</div>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        user = st.text_input("Utilizador")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Entrar", use_container_width=True)

    if submitted:
        expected_user = st.secrets.get("auth", {}).get("username", "admin1")
        expected_password = st.secrets.get("auth", {}).get("password", "doisarquitetos")
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
