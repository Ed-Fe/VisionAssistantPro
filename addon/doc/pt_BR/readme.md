# Documentação do Vision Assistant Pro

**Vision Assistant Pro** é um assistente de IA avançado e multimodal para NVDA. Ele utiliza os modelos Gemini do Google para fornecer capacidades inteligentes de leitura de tela, tradução, ditado por voz e análise de documentos.

_Este add-on foi lançado para a comunidade em homenagem ao Dia Internacional da Pessoa com Deficiência._

## 1. Configuração

Vá para **Menu NVDA > Preferências > Configurações > Vision Assistant Pro**.

- **Chave de API:** Obrigatória. Você pode inserir várias chaves (separadas por vírgulas ou por linhas). O assistente alternará automaticamente entre elas se algum limite de cota for atingido.
- **Modelo de IA:** Escolha entre os modelos **Flash** (Mais rápido/Gratuito), **Lite** ou **Pro** (Alta Inteligência).
- **URL do Proxy:** Opcional. Use se o Google estiver bloqueado em sua região. Deve ser um endereço web que funcione como ponte para a API Gemini.
- **Motor OCR:** Escolha entre **Chrome (Rápido)** para resultados rápidos ou **Gemini (Formatado)** para melhor preservação de layout e reconhecimento de tabelas.
- **Voz TTS:** Selecione o estilo de voz preferido para gerar arquivos de áudio a partir das páginas do documento.
- **Smart Swap:** Alterna automaticamente entre idiomas se o texto de origem corresponder ao idioma de destino.
- **Saída Direta:** Ignora a janela de chat e anuncia a resposta da IA diretamente via voz.
- **Integração com Área de Transferência:** Copia automaticamente a resposta da IA para a área de transferência.

## 2. Camada de Comandos & Atalhos

Para evitar conflitos de teclado, este add-on usa uma **Camada de Comandos**.

1. Pressione **NVDA + Shift + V** (Tecla Mestre) para ativar a camada (você ouvirá um bip).
2. Solte as teclas e pressione uma das teclas únicas a seguir:

| Tecla         | Função                            | Descrição                                                                              |
| ------------- | --------------------------------- | -------------------------------------------------------------------------------------- |
| **T**         | Tradutor Inteligente              | Traduz o texto sob o cursor do NVDA ou a seleção.                                      |
| **Shift + T** | Tradutor da Área de Transferência | Traduz o conteúdo atualmente na área de transferência.                                 |
| **R**         | Refinador de Texto                | Resume, Corrige Gramática, Explica ou executa **Prompts Personalizados**.              |
| **V**         | Visão de Objetos                  | Descreve o objeto atual do NVDA.                                                       |
| **O**         | Visão de Tela Completa            | Analisa todo o layout e conteúdo da tela.                                              |
| **Shift + V** | Análise de Vídeo Online           | Analisa vídeos do **YouTube**, **Instagram** ou **Twitter (X)** via URL.               |
| **D**         | Leitor de Documentos              | Leitor avançado para PDFs e imagens com seleção de intervalo de páginas.               |
| **F**         | OCR de Arquivos                   | Reconhecimento direto de texto em imagens, PDFs ou arquivos TIFF selecionados.         |
| **A**         | Transcrição de Áudio              | Transcreve arquivos MP3, WAV ou OGG para texto.                                        |
| **C**         | Solucionador de CAPTCHA           | Captura e resolve CAPTCHAs na tela ou no objeto do NVDA.                               |
| **S**         | Ditado Inteligente                | Converte fala em texto. Pressione para iniciar gravação, novamente para parar/digitar. |
| **L**         | Relatório de Status               | Anuncia o progresso atual (ex.: "Analisando...", "Ocioso").                            |
| **U**         | Verificação de Atualização        | Verifica manualmente no GitHub a versão mais recente do add-on.                        |
| **H**         | Ajuda de Comandos                 | Exibe todos os atalhos disponíveis na camada de comandos.                              |

### 2.1 Atalhos do Leitor de Documentos (Dentro do Visualizador)

Após abrir um documento com o comando **D**:

- **Ctrl + PageDown:** Avança para a próxima página (anuncia o número da página).
- **Ctrl + PageUp:** Volta para a página anterior (anuncia o número da página).
- **Alt + A:** Abre um diálogo de chat para perguntas sobre o documento.
- **Alt + R:** Força nova leitura da página atual ou de todas as páginas usando o motor Gemini.
- **Alt + G:** Gera e salva um arquivo de áudio de alta qualidade (WAV) do conteúdo.
- **Alt + S / Ctrl + S:** Salva o texto extraído como TXT ou HTML.

## 3. Prompts Personalizados & Variáveis

Abra **Configurações > Prompts > Gerenciar Prompts...** para configurar prompts do sistema e personalizados.

- **Aba Prompts Padrão:** edite prompts internos. Você pode resetar um prompt individual ou todos os padrões.
- **Aba Prompts Personalizados:** adicione, edite, remova e reorganize prompts personalizados.
- **Botão Guia de Variáveis:** abre uma janela de ajuda com todas as variáveis e tipos de entrada suportados.

### Variáveis Disponíveis

| Variável        | Descrição                                   | Tipo de Entrada   |
| --------------- | ------------------------------------------- | ----------------- |
| `[selection]`   | Texto atualmente selecionado                | Texto             |
| `[clipboard]`   | Conteúdo da área de transferência           | Texto             |
| `[screen_obj]`  | Captura de tela do objeto do NVDA           | Imagem            |
| `[screen_full]` | Captura de tela completa                    | Imagem            |
| `[file_ocr]`    | Seleciona imagem/PDF para extração de texto | Imagem, PDF, TIFF |
| `[file_read]`   | Seleciona documento para leitura            | TXT, Código, PDF  |
| `[file_audio]`  | Seleciona arquivo de áudio para análise     | MP3, WAV, OGG     |

### Exemplos de Prompts Personalizados

- **OCR Rápido:** `Meu OCR:[file_ocr]`
- **Traduzir Imagem:** `Traduzir Img:Extraia o texto desta imagem e traduza para o inglês. [file_ocr]`
- **Analisar Áudio:** `Resumo do Áudio:Ouça esta gravação e resuma os pontos principais. [file_audio]`
- **Depurador de Código:** `Depurar:Encontre bugs neste código e explique-os: [selection]`

---

**Nota:** É necessária conexão ativa com a internet para todos os recursos de IA. Documentos com várias páginas e arquivos TIFF são processados automaticamente.

## Alterações para 4.5

**Gerenciador Avançado de Prompts:** Introduzido diálogo dedicado para personalizar prompts padrão e gerenciar prompts de usuário com suporte completo para adicionar, editar, reordenar e pré-visualizar.  
**Suporte Completo a Proxy:** Resolvidos problemas de conectividade garantindo que configurações de proxy do usuário sejam aplicadas a todas as requisições de API, incluindo tradução, OCR e geração de voz.  
**Migração Automática de Dados:** Sistema inteligente de migração para atualizar prompts antigos para o formato JSON v2 na primeira execução sem perda de dados.  
**Compatibilidade Atualizada (2025.1):** Versão mínima do NVDA definida para 2025.1 devido a dependências em recursos avançados, como o Leitor de Documentos.  
**Interface de Configurações Otimizada:** Organizado o gerenciamento de prompts em diálogo separado para experiência mais limpa e acessível.  
**Guia de Variáveis em Prompts:** Guia embutido para ajudar usuários a identificar e usar variáveis dinâmicas como [selection], [clipboard], e [screen_obj].

## Alterações para 4.0.3

- **Resiliência de Rede Aprimorada:** Mecanismo de tentativa automática para conexões instáveis ou erros temporários do servidor.

- **Diálogo de Tradução Visual:** Nova janela para resultados de tradução, permitindo navegação linha a linha.
- **Visualização Formatada Agregada:** Todas as páginas processadas exibidas em uma única janela organizada.
- **Fluxo OCR Otimizado:** Ignora seleção de intervalo em documentos de uma página para maior velocidade.
- **Estabilidade da API Melhorada:** Autenticação baseada em cabeçalho para evitar erros "All API Keys failed".
- **Correções de Bugs:** Corrigidos possíveis travamentos, incluindo erro de foco no diálogo de chat.

## Alterações para 4.0.1

- **Leitor de Documentos Avançado:** Visualizador novo para PDFs e imagens com seleção de páginas, processamento em segundo plano e navegação `Ctrl+PageUp/Down`.

- **Novo Submenu de Ferramentas:** Submenu "Vision Assistant" no menu Ferramentas do NVDA.
- **Customização Flexível:** Escolha do motor OCR e voz TTS diretamente nas configurações.
- **Suporte a Múltiplas Chaves de API:** Inserção de várias chaves Gemini (uma por linha ou separadas por vírgulas).
- **Motor OCR Alternativo:** Reconhecimento confiável mesmo com limite de cota da Gemini.
- **Rotação Inteligente de Chaves de API:** Alterna automaticamente para a chave mais rápida.
- **Documento para MP3/WAV:** Gera e salva arquivos de áudio de alta qualidade dentro do leitor.
- **Suporte a Instagram Stories:** Análise e descrição usando URLs.
- **Suporte a TikTok:** Descrição visual e transcrição de clipes.
- **Diálogo de Atualização Redesenhado:** Interface acessível com caixa de rolagem para ler alterações antes da instalação.
- **Status & UX Unificados:** Padronização de diálogos e progresso em tempo real pelo comando 'L'.

## Alterações para 3.6.0

- **Sistema de Ajuda:** Comando `H` exibe lista de atalhos e funções na Camada de Comandos.

- **Análise de Vídeo Online:** Suporte a vídeos do **Twitter (X)** e melhoria na detecção de URLs.
- **Contribuição ao Projeto:** Diálogo opcional de doações para apoiar atualizações futuras.

## Alterações para 3.5.0

- **Camada de Comandos:** Introdução do sistema de Camada de Comandos (`NVDA+Shift+V`) para agrupar atalhos sob uma tecla mestre.

- **Análise de Vídeo Online:** Nova função para analisar vídeos do YouTube e Instagram via URL.

## Alterações para 3.1.0

- **Modo de Saída Direta:** Opção para ouvir respostas de IA sem abrir o diálogo de chat.

- **Integração com Área de Transferência:** Copia automaticamente respostas da IA.

## Alterações para 3.0

- **Novos Idiomas:** Adicionado Persa e Vietnamita.

- **Modelos de IA Expandidos:** Lista reorganizada com prefixos claros `[Free]`, `[Pro]`, `[Auto]`. Suporte a **Gemini 3.0 Pro** e **Gemini 2.0 Flash Lite**.
- **Estabilidade do Ditado:** Melhorias no Smart Dictation, ignorando áudios menores que 1 segundo.
- **Manipulação de Arquivos:** Corrigido upload de arquivos com nomes não ingleses.
- **Otimização de Prompts:** Melhor lógica de Tradução e resultados de Visão.

## Alterações para 2.9

- **Traduções:** Adicionadas francês e turco.

- **Visualização Formatada:** Botão "Ver Formatado" para ver conversas com estilização Markdown.
- **Configuração Markdown:** Nova opção "Limpar Markdown no Chat" para exibir sintaxe bruta se desmarcada.
- **Gerenciamento de Diálogos:** Corrigido problema de múltiplas janelas de "Refinar Texto".
- **UX Aprimorado:** Padronização de títulos de diálogos e anúncios de fala redundantes removidos.

## Alterações para 2.8

- Tradução italiana adicionada.

- **Relatório de Status:** Novo comando (NVDA+Control+Shift+I) anuncia status do add-on.
- **Exportação HTML:** Salva resultados em HTML formatado mantendo estilos.
- **Interface de Configurações:** Agrupamento acessível melhorado.
- **Novos Modelos:** Suporte a gemini-flash-latest e gemini-flash-lite-latest.
- **Idiomas:** Nepali adicionado.
- **Lógica de Menu Refine:** Corrigido bug crítico em comandos de refinar texto quando NVDA não está em inglês.
- **Ditado:** Detecção de silêncio aprimorada.
- **Atualizações de Configuração:** "Verificar atualizações ao iniciar" desabilitado por padrão.
- Limpeza de código.

## Alterações para 2.7

- Estrutura do projeto migrada para template oficial NV Access Add-on.

- Lógica de retry automático para erros HTTP 429 implementada.
- Prompts de tradução otimizados para maior precisão e melhor Smart Swap.
- Tradução russa atualizada.

## Alterações para 2.6

- Suporte a tradução russa adicionado (Obrigado ao nvda-ru).

- Mensagens de erro atualizadas para feedback mais descritivo.
- Idioma padrão alterado para inglês.

## Alterações para 2.5

- Comando OCR de Arquivo Nativo adicionado (NVDA+Control+Shift+F).

- Botão "Salvar Chat" em diálogos de resultado.
- Suporte completo a localização (i18n).
- Feedback de áudio migrado para módulo nativo de tons do NVDA.
- Mudança para Gemini File API para melhor manipulação de PDFs e áudios.
- Corrigido crash ao traduzir texto com chaves `{}`.

## Alterações para 2.1.1

- Corrigido problema com variável `[file_ocr]` em Prompts Personalizados.

## Alterações para 2.1

- Todos os atalhos padronizados para NVDA+Control+Shift eliminando conflitos.

## Alterações para 2.0

- Sistema de Auto-Atualização embutido.

- Cache de Tradução Inteligente para recuperação instantânea.
- Memória de Conversação para refinar resultados no contexto do chat.
- Comando de Tradução Dedicado para Área de Transferência (NVDA+Control+Shift+Y).
- Prompts de IA otimizados para garantir idioma de saída.
- Corrigido crash causado por caracteres especiais.

## Alterações para 1.5

- Suporte a mais de 20 novos idiomas.

- Diálogo Interativo de Refine implementado.
- Ditado Inteligente Nativo adicionado.
- Categoria "Vision Assistant" adicionada no diálogo de Gestos de Entrada do NVDA.
- Corrigidos crashes COMError em aplicativos como Firefox e Word.
- Mecanismo de retry automático para erros de servidor adicionado.

## Alterações para 1.0

- Lançamento inicial.
