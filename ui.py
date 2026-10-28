import streamlit as st

def apply_theme():
 st.markdown('''<style>
 @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
 html,body,.stApp{font-family:Inter,Arial,sans-serif;background:#0B1220;color:#F1F5F9}
 .block-container{padding-top:2rem;max-width:1600px}
 [data-testid="stSidebar"]{background:#111E30;border-right:1px solid #30435B}
 h1,h2,h3,h4,p,label{color:#F1F5F9}h1{letter-spacing:-.04em;font-weight:800!important}
 [data-testid="stCaptionContainer"] p{color:#B8C7DA!important}
 [data-testid="stMetric"]{background:#17263B;border:1px solid #30435B;border-radius:16px;padding:20px;min-height:145px}
 [data-testid="stMetricLabel"] p{color:#B8C7DA!important}
 [data-baseweb="select"]>div,input,textarea,[data-baseweb="input"],[data-baseweb="textarea"]{background:#17263B!important;color:#F1F5F9!important;border-color:#49617D!important;-webkit-text-fill-color:#F1F5F9}
 input::placeholder,textarea::placeholder{color:#B8C7DA!important;-webkit-text-fill-color:#B8C7DA}
 [data-baseweb="popover"],[data-baseweb="popover"] ul,[role="listbox"],[role="option"],[data-baseweb="calendar"]{background:#17263B!important;color:#F1F5F9!important}
 [role="option"]:hover,[role="option"][aria-selected="true"],[data-baseweb="tag"]{background:#294568!important;color:#F1F5F9!important}
 .stButton button,.stDownloadButton button,[data-testid="stFileUploaderDropzone"]{background:#17263B;color:#F1F5F9;border:1px solid #49617D;border-radius:10px}
 .stButton button:hover,.stDownloadButton button:hover{border-color:#60A5FA;color:#60A5FA}
 /* Form submissions use a separate wrapper from regular Streamlit buttons. */
 [data-testid="stFormSubmitButton"] button{background:#60A5FA!important;color:#0B1220!important;border:1px solid #60A5FA!important;border-radius:10px;min-height:44px;font-weight:700!important}
 [data-testid="stFormSubmitButton"] button *{color:inherit!important;-webkit-text-fill-color:inherit!important}
 [data-testid="stFormSubmitButton"] button:hover:not(:disabled){background:#93C5FD!important;border-color:#93C5FD!important;color:#0B1220!important}
 [data-testid="stFormSubmitButton"] button:focus-visible{outline:3px solid #FBBF24!important;outline-offset:3px}
 [data-testid="stFormSubmitButton"] button:disabled{background:#294568!important;color:#B8C7DA!important;border-color:#49617D!important;opacity:1!important;cursor:not-allowed}
 [data-testid="stDataFrame"],[data-testid="stPlotlyChart"]{border:1px solid #30435B;border-radius:14px;overflow:hidden}
 hr{border-color:#30435B}
 </style>''',unsafe_allow_html=True)

def chart(fig,key=None):
 fig.update_layout(template='plotly_dark',paper_bgcolor='#17263B',plot_bgcolor='#17263B',font=dict(family='Inter, Arial, sans-serif',color='#F1F5F9',size=13),colorway=['#60A5FA','#34D399','#FBBF24','#FB7185','#B8C7DA'],margin=dict(l=24,r=24,t=35,b=30),hoverlabel=dict(bgcolor='#0B1220',font_color='#F1F5F9',bordercolor='#60A5FA'))
 fig.update_xaxes(gridcolor='#30435B',tickfont_color='#B8C7DA')
 fig.update_yaxes(gridcolor='#30435B',tickfont_color='#B8C7DA')
 st.plotly_chart(fig,use_container_width=True,key=key)
