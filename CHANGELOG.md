# Changelog

Todas as mudancas relevantes do COMPLAT devem ser registradas neste arquivo.

O formato segue a ideia de manter entradas por versao, com secoes para adicoes, alteracoes, correcoes e detalhes tecnicos relevantes.

## [Unreleased]

### Added

- Suporte a busca por arquivos, pastas ou ambos.
- Compactacao de pastas preservando a estrutura interna.
- Modos de compressao `fast`, `balanced` e `smaller`.
- Cancelamento de analise e criacao de ZIPs.
- Escrita de ZIPs via arquivo temporario antes do rename final.
- Persistencia de preferencias locais com `QSettings`.
- Modelos Qt para tabelas de resultado.
- Filtro de resultados com debounce.
- Configuracao de Ruff para lint e formatacao.
- Documento de arquitetura.
- Guia de contribuicao.
- Guia de ambiente de desenvolvimento.

### Changed

- A analise passou a rodar fora da thread principal da interface.
- O finder passou a usar indice reutilizavel por pasta.
- O planejamento passou a reservar margem para overhead do ZIP.
- A tabela `Found` passou a indicar o tipo do item encontrado.
- A CLI passou a aceitar `--match-type`.

### Fixed

- A criacao agora evita sobrescrever ZIPs existentes.
- Arquivos parciais deixam de aparecer como resultado valido quando ocorre falha ou cancelamento.

## [0.1.0]

### Added

- Versao inicial do COMPLAT.
- Interface desktop em PySide6.
- CLI `complat`.
- Busca por arquivos a partir de lista de nomes.
- Planejamento de ZIPs com limite de tamanho.
- Criacao de multiplas partes ZIP.
- Testes automatizados iniciais.

