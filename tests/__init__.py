"""
Configuração comum dos testes.

O hash de senha usa 600 mil iterações (PBKDF2) — o certo em produção, mas
lento para dezenas de testes que criam usuários e fazem login. Aqui ele é
baixado; gerar_hash lê usuarios.ITERACOES na hora de cada chamada, e os
testes que conferem o padrão de produção usam usuarios.ITERACOES_PADRAO.
"""

from portaria import usuarios

ITERACOES_DOS_TESTES = 1_000
usuarios.ITERACOES = ITERACOES_DOS_TESTES
