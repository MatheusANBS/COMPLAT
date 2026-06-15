# Plano De Melhorias Do COMPLAT

Este documento descreve melhorias possiveis para o COMPLAT com foco em
performance, eficiencia e conforto de uso. As propostas abaixo foram baseadas
na estrutura real do projeto:

- `src/complat/domain`: regras de normalizacao, matching e planejamento.
- `src/complat/application`: casos de uso.
- `src/complat/infrastructure`: filesystem e escrita de ZIP.
- `src/complat/presentation`: CLI e interface PySide6.
- `tests`: testes de dominio, matching e criacao de ZIPs.

As melhorias estao organizadas por impacto pratico. Cada item inclui a logica
da mudanca, passos de implementacao e criterios de validacao.

## Acompanhamento Das Fases

| Fase | Melhoria | Status | Observacao |
| --- | --- | --- | --- |
| 1 | Rodar a analise fora da thread da interface | Implementado e testado | Analise executa em worker dedicado. |
| 2 | Trocar `QTableWidget` por modelos Qt | Implementado e testado | Tabelas usam model/proxy. |
| 3 | Otimizar filtro das tabelas | Implementado e testado | Proxy usa texto pesquisavel em cache e filtro com debounce de 180 ms. |
| 4 | Criar indice de pasta reutilizavel | Implementado e testado | Finder indexa nomes/stems da pasta e so calcula tamanho dos matches. |
| 5 | Adicionar cancelamento de analise e criacao | Implementado e testado | Token compartilhado, botao `Cancel` e teste dedicado de cancelamento. |
| 6 | Reduzir frequencia de sinais de progresso | Implementado e testado | Updates de bytes sao emitidos no maximo a cada 150 ms, mantendo final exato. |
| 7 | Escrever ZIPs em arquivos temporarios | Implementado e testado | Escrita usa `.zip.tmp`, rename final e bloqueia sobrescrita existente. |
| 8 | Adicionar modos de compressao | Implementado e testado | UI/CLI aceitam `fast`, `balanced`, `smaller`; `fast` evita recomprimir extensoes comuns. |
| 9 | Reservar margem para overhead do ZIP | Implementado e testado | Planner reserva margem por lote e por arquivo antes de encaixar batches. |
| 10 | Persistir preferencias do usuario | Implementado e testado | `QSettings` salva pastas, limite, recursivo, compressao, janela e splitter. |
| 11 | Melhorar qualidade de desenvolvimento | Implementado e testado | Ruff configurado, instalado no extra `dev` e validado junto com testes. |

Validacao atual do projeto:

- `ruff check src tests`
- `ruff format --check src tests`
- `compileall src tests`
- `pytest`

## 1. Rodar A Analise Fora Da Thread Da Interface

### Problema

Hoje a criacao dos ZIPs ja roda em `QThread`, mas a analise ainda e executada
diretamente pela interface em `MainWindow._analyze`. Em pastas grandes, modo
recursivo ou unidades lentas, a janela pode congelar enquanto o app escaneia a
pasta e monta o plano.

### Objetivo

Manter a interface responsiva tambem durante a etapa `Analyze plan`.

### Logica Da Solucao

Criar um worker equivalente ao `ZipCreationWorker`, mas para analise. A UI deve
apenas iniciar a thread, bloquear os botoes relevantes, exibir status e receber
o resultado por sinal.

### Passos De Implementacao

1. Criar uma classe `AnalysisWorker` em
   `src/complat/presentation/pyside/workers.py`.
2. Receber no worker:
   - `CompactFilesController`
   - pasta de origem
   - lista de nomes
   - limite em MB
3. Criar sinais:
   - `succeeded(object)`
   - `failed(str)`
   - `finished()`
4. No metodo `run`, chamar `controller.analyze(...)`.
5. Em `MainWindow`, adicionar campos:
   - `_analysis_thread`
   - `_analysis_worker`
6. Alterar `_analyze` para:
   - validar entradas
   - impedir analise concorrente
   - criar `QThread`
   - mover o worker para a thread
   - conectar sinais
   - iniciar a thread
7. Criar handlers:
   - `_on_analysis_created`
   - `_on_analysis_failed`
   - `_on_analysis_thread_finished`
8. Reusar `_render_analysis` quando a analise concluir.
9. Garantir que `_set_busy(False)` seja chamado no fim da thread.

### Validacao

- Abrir a UI, selecionar uma pasta grande e clicar em `Analyze plan`.
- Confirmar que a janela continua movel e responsiva.
- Confirmar que erros continuam aparecendo em `QMessageBox`.
- Confirmar que o botao `Create zips` so habilita apos sucesso.
- Adicionar teste manual com modo recursivo em uma pasta profunda.

## 2. Trocar QTableWidget Por Modelos Qt

### Problema

As tabelas atuais usam `QTableWidget` e criam `QTableWidgetItem` celula por
celula. Isso e simples, mas custa memoria e tempo quando ha milhares de linhas.
Tambem torna filtragem e ordenacao mais caras.

### Objetivo

Melhorar desempenho de renderizacao, ordenacao, filtragem e uso de memoria em
listas grandes.

### Logica Da Solucao

Usar `QTableView` com `QAbstractTableModel` para armazenar dados em estruturas
Python simples. Para filtro e ordenacao, usar `QSortFilterProxyModel`.

### Passos De Implementacao

1. Criar arquivo `src/complat/presentation/pyside/table_models.py`.
2. Criar um modelo base para linhas tabulares:
   - headers
   - rows
   - `rowCount`
   - `columnCount`
   - `data`
   - `headerData`
   - metodo `replace_rows`
3. Criar modelos especificos ou factories para:
   - Plan
   - Found
   - Not found
4. Substituir `QTableWidget` por `QTableView` em `MainWindow`.
5. Para cada tabela, criar:
   - model
   - proxy model
   - view
6. Ligar o campo de filtro ao proxy da aba atual.
7. Adaptar exportacao CSV para ler dados do model/proxy, nao de itens visuais.
8. Adaptar copia de celula para usar o indice selecionado da view.
9. Adaptar atualizacao de status do plano para alterar a linha no modelo.

### Validacao

- Testar com centenas e milhares de nomes.
- Confirmar que ordenacao por coluna continua funcionando.
- Confirmar que filtro funciona nas abas `Plan`, `Found` e `Not found`.
- Confirmar que exportacao CSV respeita linhas visiveis filtradas.
- Confirmar que clique em `Code` e `Name` ainda copia apenas a celula correta.

## 3. Otimizar O Filtro Das Tabelas

### Problema

O filtro atual percorre todas as linhas e concatena textos a cada tecla digitada.
Com muitas linhas, isso pode deixar a UI pesada.

### Objetivo

Deixar a busca visual rapida mesmo em resultados grandes.

### Logica Da Solucao

Combinar debounce com cache de texto pesquisavel por linha. Assim o app evita
refiltrar a cada tecla imediatamente e evita reconstruir strings repetidamente.

### Passos De Implementacao

1. Criar um `QTimer` em `MainWindow` com intervalo de 150 a 250 ms.
2. Trocar a conexao direta de `filter_input.textChanged` por:
   - atualizar o texto pendente
   - reiniciar o timer
3. Quando o timer disparar, aplicar o filtro.
4. Se a melhoria 2 for feita, implementar `filterAcceptsRow` no proxy model.
5. Armazenar em cada row uma string `search_text` ja normalizada com
   `casefold`.
6. Atualizar `search_text` apenas quando os dados da tabela forem substituidos.

### Validacao

- Digitar rapidamente no filtro e confirmar que a UI nao engasga.
- Confirmar que filtros parciais continuam funcionando.
- Confirmar que limpar o campo restaura todas as linhas.

## 4. Criar Indice De Pasta Reutilizavel

### Problema

`LocalFileFinder` possui cache por pasta, modo recursivo e conjunto exato de
nomes. Se o usuario altera um nome na lista, o cache nao reaproveita o scan
anterior e a pasta pode ser varrida de novo.

### Objetivo

Escanear a pasta uma vez e reaproveitar o indice para diferentes listas de
nomes.

### Logica Da Solucao

Separar o cache em duas etapas:

1. Indice da pasta:
   - chave: pasta resolvida + modo recursivo
   - valor: mapa de nome normalizado para candidatos
2. Consulta:
   - receber nomes desejados
   - buscar diretamente no indice

### Passos De Implementacao

1. Criar uma estrutura interna como `FolderIndex`.
2. Durante o scan, preencher chaves para:
   - nome completo do arquivo normalizado
   - stem normalizado
3. Guardar tambem metadados de invalidacao:
   - quantidade de arquivos lidos
   - data do scan
   - talvez `mtime` da pasta raiz
4. Alterar `LocalFileFinder.find` para:
   - obter ou criar indice da pasta
   - buscar apenas os nomes solicitados
   - remover duplicatas por path
5. Manter limite de cache LRU por pasta, por exemplo 4 ou 8 indices.
6. Adicionar metodo opcional `clear_cache`.

### Validacao

- Criar teste para duas consultas diferentes na mesma pasta.
- Confirmar que ambas retornam resultados corretos.
- Confirmar que arquivos duplicados por filename/stem nao aparecem duas vezes.
- Medir manualmente segunda analise com lista alterada pequena.

## 5. Adicionar Cancelamento De Analise E Criacao

### Problema

Operacoes longas nao podem ser canceladas pelo usuario. Se uma pasta for muito
grande ou uma geracao for iniciada por engano, o usuario precisa esperar.

### Objetivo

Permitir cancelar com seguranca, sem corromper a UI e sem deixar ZIP final
parcial como se estivesse valido.

### Logica Da Solucao

Criar um token de cancelamento compartilhado entre UI, caso de uso e adapters.
O token e checado em pontos seguros: entre arquivos, entre diretorios e entre
chunks de escrita.

### Passos De Implementacao

1. Criar classe `CancellationToken` em uma camada neutra, por exemplo
   `application/cancellation.py`.
2. A classe deve ter:
   - `cancel()`
   - `is_cancelled`
   - `raise_if_cancelled()`
3. Criar excecao `OperationCancelled` em `application/errors.py`.
4. Aceitar token opcional em:
   - `LocalFileFinder.find`
   - `ZipArchiveWriter.write_batch`
   - `CreateZipBatchesUseCase.execute_from_analysis`
   - workers PySide
5. Na UI, trocar o botao de acao por `Cancel` durante operacao ou adicionar um
   botao dedicado.
6. Ao cancelar ZIP:
   - parar novas escritas
   - fechar handles abertos
   - apagar arquivos temporarios
   - mostrar status `Cancelled`
7. Ao cancelar analise:
   - liberar botoes
   - preservar inputs
   - nao habilitar `Create zips`

### Validacao

- Cancelar durante analise recursiva.
- Cancelar durante escrita de arquivo grande.
- Confirmar que nao sobra `.tmp` ou ZIP parcial final.
- Confirmar que uma nova operacao pode ser iniciada depois.

## 6. Reduzir Frequencia De Sinais De Progresso

### Problema

O writer envia progresso a cada chunk de 1 MB. Em criacoes paralelas, isso pode
gerar muitos sinais para a thread da UI.

### Objetivo

Manter progresso fluido sem sobrecarregar a interface.

### Logica Da Solucao

Agrupar deltas de bytes e emitir progresso por intervalo de tempo ou tamanho
acumulado.

### Passos De Implementacao

1. Criar classe pequena `ProgressThrottler`.
2. Configurar limites:
   - intervalo minimo: 100 a 200 ms
   - bytes minimos acumulados: opcional
3. Em `ZipArchiveWriter._write_file`, enviar bytes ao throttler.
4. Garantir flush final ao terminar cada arquivo.
5. Preservar total correto no `CreateZipBatchesUseCase`.

### Validacao

- Gerar ZIPs com arquivos grandes.
- Confirmar que barra progride suavemente.
- Confirmar que o progresso termina em 100%.
- Confirmar que mensagens ainda indicam arquivo/parte atual.

## 7. Escrever ZIPs Em Arquivos Temporarios

### Problema

O writer grava direto em `complat_part_###.zip`. Se a operacao falhar ou for
cancelada, pode sobrar arquivo parcial. Alem disso, uma geracao pode sobrescrever
arquivos existentes sem confirmacao clara.

### Objetivo

Tornar a criacao atomica e mais segura.

### Logica Da Solucao

Escrever cada parte como arquivo temporario no mesmo diretorio. Depois de fechar
o ZIP e validar tamanho, renomear para o nome final.

### Passos De Implementacao

1. Em `ZipArchiveWriter.write_batch`, definir:
   - `final_path`
   - `temp_path`, por exemplo `complat_part_001.zip.tmp`
2. Escrever o ZIP em `temp_path`.
3. Medir tamanho real de `temp_path`.
4. Se passar na validacao, renomear para `final_path`.
5. Se falhar, apagar `temp_path`.
6. Decidir politica de arquivo existente:
   - sobrescrever somente com confirmacao da UI
   - ou gerar nome unico
7. Adicionar checagem previa em `CreateZipBatchesUseCase` ou controller para
   detectar colisao de saida.

### Validacao

- Simular falha durante escrita e confirmar limpeza.
- Gerar novamente na mesma pasta e confirmar comportamento esperado.
- Confirmar que arquivos finais so aparecem apos ZIP valido.

## 8. Adicionar Modos De Compressao

### Problema

O app usa `ZIP_DEFLATED` com `compresslevel=1`. E um bom default para velocidade,
mas nem todo tipo de arquivo se beneficia de compressao. PDFs, imagens e
arquivos ja compactados podem gastar CPU sem reduzir tamanho.

### Objetivo

Dar controle ao usuario e melhorar previsibilidade de tempo/tamanho.

### Logica Da Solucao

Adicionar modos:

- `Fast`: usa `ZIP_STORED` para extensoes ja compactadas e `compresslevel=1`
  para o resto.
- `Balanced`: `ZIP_DEFLATED` com nivel medio.
- `Smaller`: `ZIP_DEFLATED` com nivel maior.

### Passos De Implementacao

1. Criar enum ou dataclass `CompressionMode`.
2. Atualizar `ZipArchiveWriter` para receber modo de compressao.
3. Implementar decisao por arquivo:
   - `.pdf`, `.jpg`, `.jpeg`, `.png`, `.zip`, `.rar`, `.7z`, `.mp4` podem usar
     `ZIP_STORED` no modo rapido.
4. Adicionar seletor na UI.
5. Adicionar argumento CLI, por exemplo `--compression fast|balanced|smaller`.
6. Passar a opcao pelo `build_services`.
7. Documentar o trade-off no README.

### Validacao

- Testar cada modo com arquivos texto e PDFs.
- Confirmar que os ZIPs abrem normalmente.
- Medir tempo e tamanho final de cada modo.

## 9. Reservar Margem Para Overhead Do ZIP No Planejamento

### Problema

O planner usa tamanho de origem como estimativa. Depois, a criacao verifica o
tamanho real do ZIP. Em casos perto do limite, o ZIP pode exceder o maximo por
causa de metadados internos.

### Objetivo

Reduzir falhas de criacao quando o plano esta muito proximo do limite.

### Logica Da Solucao

Subtrair uma reserva por arquivo e por batch antes de decidir se um arquivo cabe
em uma parte.

### Passos De Implementacao

1. Criar constantes no `ZipPlanner`, por exemplo:
   - overhead por arquivo
   - overhead por batch
   - margem percentual opcional
2. Calcular `effective_max_size_bytes`.
3. Usar tamanho planejado como:
   - tamanho do arquivo
   - mais overhead estimado do arquivo
4. Guardar no plano a estrategia/margem usada.
5. Exibir na aba `Heuristic` que ha margem de seguranca.

### Validacao

- Criar teste com varios arquivos pequenos perto do limite.
- Confirmar que o plano fica um pouco mais conservador.
- Confirmar que arquivos individuais maiores que o limite continuam gerando
  erro esperado.

## 10. Persistir Preferencias Do Usuario

### Problema

O usuario precisa reconfigurar pasta, limite, modo recursivo e tamanho da janela
a cada abertura.

### Objetivo

Deixar o uso diario mais confortavel.

### Logica Da Solucao

Usar `QSettings` para salvar preferencias locais da UI.

### Passos De Implementacao

1. Configurar organizacao e nome do app em `pyside_app.py`.
2. Em `MainWindow`, carregar ao iniciar:
   - ultima pasta de origem
   - ultima pasta de saida
   - limite MB
   - modo recursivo
   - geometria da janela
   - estado do splitter
3. Salvar quando:
   - o usuario altera campos
   - a janela fecha
4. Implementar `closeEvent` para salvar geometria e splitter.
5. Evitar salvar lista de nomes por padrao, pois pode conter dados sensiveis.

### Validacao

- Abrir app, alterar preferencias, fechar e abrir novamente.
- Confirmar que valores voltam corretamente.
- Confirmar que nomes colados nao sao persistidos automaticamente.

## 11. Melhorar Qualidade De Desenvolvimento

### Problema

O projeto ja possui testes, mas ainda nao ha configuracao explicita de lint,
formatacao e tipagem. Tambem existem declaracoes duplicadas de versao e
dependencias.

### Objetivo

Reduzir regressao e facilitar manutencao.

### Logica Da Solucao

Adicionar ferramentas leves que combinam com o projeto atual.

### Passos De Implementacao

1. Adicionar `ruff` em `[project.optional-dependencies].dev`.
2. Configurar `ruff` no `pyproject.toml`.
3. Opcionalmente adicionar `mypy` ou `pyright`.
4. Adicionar comandos documentados:
   - `python -m pytest`
   - `python -m ruff check src tests`
   - `python -m ruff format src tests`
5. Centralizar versao:
   - usar `importlib.metadata.version("complat")`
   - ou manter `__version__` como fonte unica
6. Evitar duplicar dependencias entre `requirements.txt` e `pyproject.toml`, ou
   documentar qual e a fonte oficial.

### Validacao

- Rodar testes.
- Rodar lint.
- Confirmar que build com PyInstaller continua funcionando.

## Ordem Recomendada

1. Analise em background.
2. Tabelas com model/proxy.
3. Filtro com debounce/cache.
4. Indice reutilizavel de pasta.
5. Cancelamento.
6. ZIP temporario e protecao contra sobrescrita.
7. Throttle de progresso.
8. Modos de compressao.
9. Margem de overhead no planner.
10. Preferencias com `QSettings`.
11. Ruff, tipagem e limpeza de configuracao.

Essa ordem prioriza primeiro o conforto percebido pelo usuario e depois reduz
riscos de operacoes longas e manutencao futura.
