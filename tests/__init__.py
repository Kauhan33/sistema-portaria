"""
Configuração comum dos testes.

O hash de senha usa 600 mil iterações (PBKDF2) — o certo em produção, mas
lento para dezenas de testes que criam usuários e fazem login. Aqui ele é
baixado; gerar_hash lê senhas.ITERACOES na hora de cada chamada, e os
testes que conferem o padrão de produção usam senhas.ITERACOES_PADRAO.
"""

from portaria import senhas

ITERACOES_DOS_TESTES = 1_000
senhas.ITERACOES = ITERACOES_DOS_TESTES
