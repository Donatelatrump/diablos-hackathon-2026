"""One navigation state shared by the menu and in-page actions."""
import streamlit as st

VIEWS = [
    ('Inicio', 'Simulador'),
    ('Simular y comparar v9', 'Comparar estadios'),
    ('Lanzadores', 'Lanzadores'),
    ('Confianza', 'Confianza'),
    ('Entender el proyecto', 'Ayuda'),
]


def open_view(view):
    st.session_state['main_navigation'] = view


def render_navigation():
    view = st.session_state.get('main_navigation', 'Inicio')
    st.session_state['main_navigation'] = view
    with st.container(key='main-menu'):
        for column, (value, label) in zip(st.columns(len(VIEWS)), VIEWS):
            column.button(label, key='nav-' + value, use_container_width=True,
                type='primary' if view == value else 'secondary',
                on_click=open_view, args=(value,))
        label = dict(VIEWS).get(view, 'Resultados históricos')
        st.markdown(f'<span class="nav-current" role="status">Vista actual: {label}</span>', unsafe_allow_html=True)
    return view
