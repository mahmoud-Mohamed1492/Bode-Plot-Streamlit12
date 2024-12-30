# libraries
import streamlit as st
import numpy as np
import control as ctl
import matplotlib.pyplot as plt
import sympy as sym








##########################################################################

def is_zeros(list):
    l = len(list)
    decide = 0
    for i in range(l):
        if list[i] != 0:
            decide += 1
    if decide == 0:
        return True
    else:
        return False        

###########################################################################
######################## Main Function ####################################
###########################################################################

##Functions
def plot_margins(sys, wl = 0.01, wu = 1000):
    w_lower = wl
    w_upper = wu
    mag,phase,omega = ctl.bode(sys,dB=True,plot=False,omega_limits=[w_lower,w_upper])
    magdB = 20*np.log10(mag)
    phase_deg = phase*180.0/np.pi
    Gm,Pm,Wcg,Wcp = ctl.margin(sys)
    GmdB = 20*np.log10(Gm)
    ##Plot Gain and Phase
    f,(ax1,ax2) = plt.subplots(2,1)
    ax1.semilogx(omega,magdB)
    ax1.grid(which="both")
    #ax1.set_yticks(range(-100,51,20))
    #ax1.set_ylim(-120,50)
    ax1.set_xlim(w_lower,w_upper)
    ax1.set_xlabel('Frequency (rad/s)')
    ax1.set_ylabel('Magnitude (dB)')
    ax2.semilogx(omega,phase_deg)
    #ax2.set_yticks(range(-675,-45,45))
    #ax2.set_ylim(None, None)
    ax2.set_xlim(w_lower,w_upper)
    ax2.grid(which="both")
    ax2.set_xlabel('Frequency (rad/s)')
    ax2.set_ylabel('Phase (deg)')
    ax1.set_title('Gm = '+str(np.round(GmdB,2))+' dB (at '+str(np.round(Wcg,2))+' rad/s), Pm = '+str(np.round(Pm,2))+' deg (at '+str(np.round(Wcp,2))+' rad/s)')
    ###Plot the zero dB line
    ax1.plot(omega,0*omega,'k--',lw=2)
    ###Plot the -180 deg lin
    ax2.plot(omega,-180+0*omega,'k--',lw=2)
    ##Plot the vertical line from -180 to 0 at Wcg
    ax2.plot([Wcg,Wcg],[-180,0],'r--',lw=2)
    ##Plot the vertical line from -180+Pm to 0 at Wcp
    ax2.plot([Wcp,Wcp],[-180+Pm,0],'g--',lw=2)
    ##Plot the vertical line from min(magdB) to 0-GmdB at Wcg
    ax1.plot([Wcg,Wcg],[np.min(magdB),0-GmdB],'r--',lw=2)
    ##Plot the vertical line from min(magdB) to 0db at Wcp
    ax1.plot([Wcp,Wcp],[np.min(magdB),0],'g--',lw=2)

    f.set_figwidth(15)
    f.set_figheight(10)
    st.pyplot(f)
    return Gm,Pm,Wcg,Wcp


# Sidebar

st.sidebar.title("**⚒️Main Menu⚒️**")
section = st.sidebar.selectbox("**Choose Your Model:**",
    ["Model 01", "Model 02","Model 03"])

section2 = st.sidebar.radio("**Options:**", (True, False), 1)

# Model 01 Section
if section == "Model 01":
    st.write("""<h4 style='text-align: center;
    '>Model 01</h4>""", unsafe_allow_html=True)
    st.image('src/model 01.png')
    m = st.slider('Enter value of m',0,10,0)
    n = st.slider('Enter value of n',0,10,0)
    num = []
    denum = []
    if (m != 0) or (n != 0):
        st.write("""<h8 style='text-align: center;
    '>Numerator Data</h8>""", unsafe_allow_html=True)
        for i in range(m+1):
            num.append(st.number_input(f'Enter a{i}'))
        st.write("""<h8 style='text-align: center;
    '>Denumerator Data</h8>""", unsafe_allow_html=True)
        for i in range(n+1):
            denum.append(st.number_input(f'Enter b{i}'))    

        if st.button('Submit'):
    
            G = ctl.tf(num,denum)
            #(num,den) = ctl.pade(0.1,3)
            #Gp = ctl.tf(num,den)*G
            Gm,Pm,Wcg,Wcp=plot_margins(G)

        if section2:
            st.write("""<h4 style='text-align: center;
            '>Change Omega Range</h4>""", unsafe_allow_html=True)
            w_l = st.number_input('Enter Lower Limit of w:')
            w_u = st.number_input('Enter Upper Limit of w:')
            if (w_l >= 1e-15) or (w_u != 0):
                G = ctl.tf(num,denum)
                Gm,Pm,Wcg,Wcp=plot_margins(G, wl=w_l, wu= w_u)    


elif section == 'Model 02':
    st.write("""<h4 style='text-align: center;
    '>Model 02</h4>""", unsafe_allow_html=True)
    st.image('src/model 02.png')
    m = st.slider('Enter Number of Round Bracket in the numerator:',1,10,1)
    n = st.slider('Enter Number of Round Bracket in the denumerator:',1,10,1)
    num_a = []
    num_b = []
    denum_c = []
    denum_d = []
    num = []
    denum = []
    s = sym.symbols('S')
    expr_num = 1
    expr_denum = 1
    if (m != 0) or (n != 0):
        st.write("""<h8 style='text-align: center;
    '>Numerator Data</h8>""", unsafe_allow_html=True)
        for i in range(m):
            c1, c2= st.columns(2)
            with c1:
                num_a.append(st.number_input(f'Enter a{i}', value=1.00))
            with c2:    
                num_b.append(st.number_input(f'Enter b{i}'))

        for i,j in zip(num_a,num_b):
            expr_num *= (i * s + j)
        expr_expand = sym.expand(expr_num)
        for i in range(m,-1,-1):
            num.append(float(expr_expand.coeff(s, i)))    
        st.write("""<h8 style='text-align: center;
    '>Denumerator Data</h8>""", unsafe_allow_html=True)
        for i in range(n):
            c1, c2= st.columns(2)
            with c1:
                denum_c.append(st.number_input(f'Enter c{i}', value=1.00))
            with c2:    
                denum_d.append(st.number_input(f'Enter d{i}'))  

        for i,j in zip(denum_c,denum_d):
            expr_denum *= (i * s + j)
        expr_deexpand = sym.expand(expr_denum)
        for i in range(n,-1,-1):
            denum.append(float(expr_deexpand.coeff(s, i)))   

        if st.button('Submit'):
    
            G = ctl.tf(num,denum)
            #(num,den) = ctl.pade(0.1,3)
            #Gp = ctl.tf(num,den)*G
            Gm,Pm,Wcg,Wcp=plot_margins(G)

        if section2:
            st.write("""<h4 style='text-align: center;
            '>Change Omega Range</h4>""", unsafe_allow_html=True)
            w_l = st.number_input('Enter Lower Limit of w:')
            w_u = st.number_input('Enter Upper Limit of w:')
            if (w_l >= 1e-15) or (w_u != 0):
                G = ctl.tf(num,denum)
                Gm,Pm,Wcg,Wcp=plot_margins(G, wl=w_l, wu= w_u)    


elif section == 'Model 03':
    st.write("""<h4 style='text-align: center;
    '>Model 02</h4>""", unsafe_allow_html=True)
    st.image('src/model 03.png')
    k = st.number_input('Enter Value of K:', value=0.00)
    m = st.slider('Enter Number of Round Bracket in the numerator:',1,10,1)
    n = st.slider('Enter Number of Round Bracket in the denumerator:',1,10,1)
    num_a = []
    num_b = []
    denum_c = []
    denum_d = []
    num = []
    denum = []
    s = sym.symbols('S')
    expr_num = 1
    expr_denum = 1
    if (m != 0) or (n != 0):
        st.write("""<h8 style='text-align: center;
    '>Numerator Data</h8>""", unsafe_allow_html=True)
        for i in range(m):
            c1, c2= st.columns(2)
            with c1:
                num_a.append(st.number_input(f'Enter a{i}', value=1.00))
            with c2:    
                num_b.append(st.number_input(f'Enter b{i}'))

        for i,j in zip(num_a,num_b):
            expr_num *= (i * s + j)
        expr_expand = sym.expand(expr_num)
        for i in range(m,-1,-1):
            num.append(float(expr_expand.coeff(s, i)))    

        st.write("""<h8 style='text-align: center;
    '>Denumerator Data</h8>""", unsafe_allow_html=True)
        for i in range(n):
            c1, c2= st.columns(2)
            with c1:
                denum_c.append(st.number_input(f'Enter c{i}', value=1.00))
            with c2:    
                denum_d.append(st.number_input(f'Enter d{i}'))  

        for i,j in zip(denum_c,denum_d):
            expr_denum *= (i * s + j)
        expr_deexpand = sym.expand(expr_denum)
        for i in range(n,-1,-1):
            denum.append(float(expr_deexpand.coeff(s, i)))   

        if st.button('Submit'):
    
            G = ctl.tf(num,denum)
            (num,den) = ctl.pade(k,3)
            Gp = ctl.tf(num,den)*G
            Gm,Pm,Wcg,Wcp=plot_margins(Gp)

        if section2:
            st.write("""<h4 style='text-align: center;
            '>Change Omega Range</h4>""", unsafe_allow_html=True)
            w_l = st.number_input('Enter Lower Limit of w:')
            w_u = st.number_input('Enter Upper Limit of w:')
            if (w_l >= 1e-15) or (w_u != 0):
                G = ctl.tf(num,denum)
                (num,den) = ctl.pade(k,3)
                Gp = ctl.tf(num,den)*G
                Gm,Pm,Wcg,Wcp=plot_margins(Gp, wl=w_l, wu= w_u)    





