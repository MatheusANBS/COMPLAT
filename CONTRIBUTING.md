# Contribuindo

Obrigado por contribuir com o COMPLAT. Este guia descreve o fluxo recomendado para trabalhar no projeto com seguranca e consistencia.

## Preparar O Ambiente

Consulte [SETUP_ENVIRONMENT.md](SETUP_ENVIRONMENT.md) para instalar dependencias, configurar o ambiente virtual e executar a aplicacao localmente.

## Fluxo De Trabalho

1. Crie uma branch a partir da branch principal.
2. Faca alteracoes pequenas e coesas.
3. Adicione ou atualize testes quando houver mudanca de comportamento.
4. Rode formatacao, lint e testes antes de enviar.
5. Abra um pull request com resumo claro e passos de validacao.

Exemplo:

```bash
git checkout -b feature/match-folders
```

## Padroes De Codigo

- Siga a arquitetura em camadas descrita em [ARCHITECTURE.md](ARCHITECTURE.md).
- Mantenha regras de dominio fora da UI.
- Prefira casos de uso e portas existentes antes de criar novas dependencias diretas.
- Use nomes claros e mantenha funcoes pequenas quando possivel.
- Evite refatoracoes nao relacionadas ao objetivo da mudanca.

## Validacao Local

Execute:

```powershell
.venv\Scripts\python.exe -m ruff format src tests
.venv\Scripts\python.exe -m ruff check src tests
.venv\Scripts\python.exe -m pytest
```

Para uma verificacao sem alterar arquivos:

```powershell
.venv\Scripts\python.exe -m ruff format --check src tests
```

## Testes

Adicione testes para:

- novas regras de matching;
- alteracoes no planejamento de ZIP;
- comportamento de filesystem;
- escrita ou validacao de arquivos ZIP;
- erros esperados e cancelamento.

## Pull Requests

Um bom pull request deve incluir:

- objetivo da mudanca;
- principais arquivos alterados;
- riscos ou limites conhecidos;
- comandos executados para validacao.

Se a mudanca alterar o uso do aplicativo, atualize o [README.md](README.md).

