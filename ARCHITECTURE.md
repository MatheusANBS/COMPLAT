# Arquitetura

Este documento descreve a arquitetura do COMPLAT, um aplicativo desktop local para localizar arquivos ou pastas por uma lista de nomes, montar um plano de ZIPs por limite de tamanho e gerar os arquivos finais de forma controlada.

## Visao Geral

O COMPLAT segue uma organizacao em camadas inspirada em Clean Architecture. A regra principal e manter as decisoes de negocio independentes da interface grafica, do filesystem e da biblioteca de ZIP.

```text
src/complat/
  domain/             Regras puras de dominio
  application/        Casos de uso e portas
  infrastructure/     Adaptadores de filesystem e ZIP
  presentation/       CLI, UI PySide6 e composition root
  assets/             Icone e imagem do aplicativo
tests/                Testes automatizados
```

Direcao das dependencias:

```text
presentation -> application -> domain
infrastructure -> application/domain
```

As camadas `domain` e `application` nao conhecem PySide6, `zipfile` ou detalhes visuais da aplicacao.

## Camadas

### Domain

Arquivos principais:

- `src/complat/domain/entities.py`
- `src/complat/domain/services.py`

Responsabilidades:

- Representar candidatos encontrados, lotes de ZIP e resultados de matching.
- Normalizar nomes informados pelo usuario.
- Comparar nomes contra arquivos ou pastas encontrados.
- Planejar os lotes ZIP usando best-fit decreasing com margem de seguranca para overhead do ZIP.

### Application

Arquivos principais:

- `src/complat/application/use_cases.py`
- `src/complat/application/ports.py`
- `src/complat/application/errors.py`
- `src/complat/application/cancellation.py`

Responsabilidades:

- Orquestrar os casos de uso.
- Expor contratos para busca local e escrita de arquivos ZIP.
- Controlar cancelamento de operacoes longas.
- Validar condicoes esperadas, como arquivo maior que o limite ou ZIP de saida ja existente.

### Infrastructure

Arquivos principais:

- `src/complat/infrastructure/filesystem.py`
- `src/complat/infrastructure/zip_writer.py`

Responsabilidades:

- Escanear pastas usando `os.scandir`.
- Indexar arquivos, pastas ou ambos conforme o modo selecionado.
- Calcular tamanho de pastas de forma recursiva.
- Escrever ZIPs em arquivo temporario e renomear somente apos sucesso.
- Preservar estrutura interna de pastas compactadas.
- Aplicar modos de compressao `fast`, `balanced` e `smaller`.

### Presentation

Arquivos principais:

- `src/complat/presentation/cli.py`
- `src/complat/presentation/composition.py`
- `src/complat/presentation/pyside_app.py`
- `src/complat/presentation/pyside/main_window.py`
- `src/complat/presentation/pyside/workers.py`
- `src/complat/presentation/pyside/table_models.py`

Responsabilidades:

- Fornecer interface CLI e interface desktop.
- Compor os servicos concretos da aplicacao.
- Rodar analise e criacao de ZIPs fora da thread principal da UI.
- Exibir plano, encontrados, nao encontrados e estrategia usada.
- Exportar resultados visiveis em CSV.

## Fluxo Principal

1. O usuario seleciona pasta de origem, pasta de saida, limite por ZIP e modo de busca.
2. O usuario cola a lista de nomes.
3. A UI inicia a analise em background.
4. O caso de uso normaliza os nomes e consulta o `LocalFileFinder`.
5. O finder retorna candidatos encontrados.
6. O matcher separa encontrados e nao encontrados.
7. O planner monta os lotes ZIP.
8. A UI mostra o plano e habilita a criacao.
9. A criacao roda em background e escreve cada ZIP em `.tmp`.
10. Ao concluir com sucesso, o arquivo temporario e renomeado para `complat_part_###.zip`.

## Modos De Busca

O COMPLAT suporta tres modos:

- `files`: busca apenas arquivos.
- `folders`: busca apenas pastas.
- `both`: busca arquivos e pastas.

Pastas encontradas sao tratadas como uma unidade no planejamento. Durante a criacao, o conteudo interno e compactado preservando caminhos relativos.

## Cancelamento E Seguranca

Operacoes longas recebem um `CancellationToken`. O token e checado durante:

- analise;
- scan de pastas;
- calculo de tamanho de diretorios;
- planejamento;
- escrita dos arquivos ZIP.

A escrita de ZIP usa arquivo temporario no mesmo diretorio de destino. Se a operacao falhar ou for cancelada, o temporario e removido.

## Testes

Os testes ficam em `tests/` e cobrem:

- normalizacao e matching de nomes;
- planejamento de ZIPs;
- criacao de multiplas partes;
- progresso por bytes;
- cancelamento;
- protecao contra sobrescrita;
- escrita temporaria;
- modos de compressao;
- busca e compactacao de pastas.

