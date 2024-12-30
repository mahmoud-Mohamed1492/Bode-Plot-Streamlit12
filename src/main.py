import sympy as sym

a = [0]
b = [10]
c = [1 , 1]
d = [4 , 1]
denum = []
s = sym.symbols('S')
expr_denum = 1
# for i,j in zip(a,b):
#     expr *= (i * s + j)
# expr_expand = sym.expand(expr)
# for i in range(len(a),-1,-1):
#     D.append(expr_expand.coeff(s, i))    
# print(D)


for i,j in zip(c,d):
    expr_denum *= (i * s + j)
expr_deexpand = sym.expand(expr_denum)
for i in range(2,-1,-1):
    denum.append(expr_deexpand.coeff(s, i))  

print(denum)      
# expr = (s+1) * (s+2)
# print(expr)
# expr_expand = sym.expand(expr)
# print(expr_expand)

# print(expr_expand.coeff(s, 0))