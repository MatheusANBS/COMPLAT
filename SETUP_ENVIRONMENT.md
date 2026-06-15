# Ambiente De Desenvolvimento

Este guia descreve como configurar o ambiente local para desenvolver, testar e executar o COMPLAT.

## Requisitos

- Windows.
- Python 3.11 ou superior.
- PowerShell.
- Git.

O projeto nao depende de Node.js, npm, Docker ou banco de dados.

## Configuracao Rapida

Na raiz do projeto, execute:

```powershell
.\setup.ps1
```

O script cria o ambiente virtual local, instala dependencias e registra os launchers `complat` e `complat-ui`.

Para evitar alterar o `PATH` do usuario:

```powershell
.\setup.ps1 -NoGlobalCommands
```

## Executar A Interface Desktop

Depois do setup:

```powershell
.\complat-ui
```

Ou, em um terminal novo quando o PATH global estiver configurado:

```powershell
complat-ui
```

## Executar A CLI

```powershell
.\complat --help
```

Exemplo de analise:

```powershell
.\complat `
  --folder "C:\Files" `
  --names-file ".\names.txt" `
  --max-mb 9 `
  --analyze-only
```

Exemplo com pastas:

```powershell
.\complat `
  --folder "C:\Files" `
  --names-file ".\names.txt" `
  --output-folder ".\zips" `
  --match-type folders
```

## Validacao

Rode testes:

```powershell
.venv\Scripts\python.exe -m pytest
```

Rode lint:

```powershell
.venv\Scripts\python.exe -m ruff check src tests
```

Verifique formatacao:

```powershell
.venv\Scripts\python.exe -m ruff format --check src tests
```

Aplicar formatacao:

```powershell
.venv\Scripts\python.exe -m ruff format src tests
```

## Gerar Executavel

```powershell
.\build_exe.ps1 -Clean
```

O resultado esperado e:

```text
dist/COMPLAT/COMPLAT.exe
```

Distribua a pasta inteira `dist/COMPLAT/`.

## Problemas Comuns

Se `complat-ui` nao for reconhecido, abra um novo terminal. Alteracoes de `PATH` nao afetam terminais ja abertos.

Se o PowerShell bloquear scripts, ajuste a politica do usuario:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

