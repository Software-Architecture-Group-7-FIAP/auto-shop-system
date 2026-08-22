# DOCUMENTO CENTRALIZADO DE REQUISITOS FUNCIONAIS

Total de requisitos consolidados: 40
==================================================

## REQUISITO FUNCIONAL: RF01
--------------------------------------------------
Titulo: O Sistema deve permitir a Gestão do Cliente
Descrição: Descreve a sequência de funções realizadas para o cadastro de um cliente no sistema

| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | x |
| **Pré Condições** | Informações Essenciais |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|   1. Logado no sistema, acessa Clientes |  |
| 2. Informa: Nome, Se pessoa jurídica ou física, CPF ou CNPJ, telefone, email, endereço.  |  |
|  | 3. Verifica se CPF ou CNPJ já existe no sistema |
|  | 4. Valida CPF ou CNPJ |
|  | 5. Cadastra cliente no sistema salvando todas as informações de 2. na base de dados  |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| 2.1. Informa CPF ou CNPJ do cliente e pesquisa se já existe no sistema
3.1 CPF informado no cadastro já existe no sistema |  |
|  | 2.2 e 3.2 Retorna Registro com informações do cliente  |
| 4.1 CPF ou CNPJ é inválido |  |
|  | 4.2 Retorna mensagem de erro: Cliente inválido.  |

| **Pós Condição** | O cliente não pode estar associado a um CPF, CNPJ previamente cadastrado no sistema |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF02
--------------------------------------------------
Titulo: O Sistema deve permitir a Gestão do Veículo
Descrição: Descreve a sequência de funções realizadas para o cadastro de um novo veículo no sistema.

| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | x |
| **Pré Condições** | Cliente Cadastrado: RF01, Informações essenciais do veículo |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|   1. Logado no sistema, acessa Cliente/Veículo |  |
|  | .2. Lista todos os veículos associados ao cliente |
|  | 3. Exibe a opção Adicionar Novo |
| 4. Clica em Adicionar Novo |  |
|  | 5. Abre formulário de cadastro |
| 6. Informa: Placa, UF, Cidade, Marca/Modelo, Cor, Ano de Fabricação |  |
|  | 7. Verifica a placa |
|  | 8. Verifica se veículo já existe para o cliente |
|  | 9. Registra todas as informações de 6. na base de dados |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| 2.1 Veículo já existe para o cliente
8.1 Veículo já existe para o cliente |  |
|  | 2.2 - Retorna informações do veículo
8.2 - Retorna informações do veículo |
| 7.1 Placa inválida |  |
|  | 7.2 Retorna erro: veículo inválido |

| **Pós Condição** | Não pode haver dois veículos registrados com a mesma placa para o mesmo cliente.  |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF03
--------------------------------------------------
Titulo: O Sistema deve permitir a Gestão de Produtos (Peças e Insumos)
Descrição: Descreve a sequência de funções realizadas para o cadastro de um novo produto no sistema

| **Ator Principal** | Estoquista |
| --- | --- |
| **Atores Secundários** | Atendente |
| **Pré Condições** | x |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|   1. Logado no sistema, acessa Produtos |  |
|  | 2. Lista produtos cadastrados no sistema |
|  | 3. Exibe opção de adicionar novo |
| 4. Clica na opção adicionar novo |  |
|  | 5. Exibe formulário de registro de produtos |
| 6. Informa: Nome, descrição, preço unitário, código de barra |  |
|  | 7. Verifica se já existe um produto com código de barra cadastrado no sistema |
|  | 8. Registra as informações de 6.1 na base de dados |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| 7.1 Produto já cadastrado |  |
|  | 7.2 Retorna informações do produto |

| **Pós Condição** | Não pode haver dois produtos com o mesmo código de barras registrado no sistema.  |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF04
--------------------------------------------------
Titulo: O Sistema deve permitir a Gestão de Serviços
Descrição: Descreve a sequência de funções realizadas para o cadastro de um novo serviço no sistema

| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | x |
| **Pré Condições** | x |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|   1. Logado no sistema, acessa Serviços |  |
|  | 2. Lista serviços cadastrados no sistema |
|  | 3. Exibe opção de adicionar novo |
| 4. Clica na opção adicionar novo |  |
|  | 5. Exibe formulário de registro de serviços |
| 6. Informa: Nome, descrição, preço unitário, produtos relacionados |  |
|  | 7. Registra as informações de 6.1 na base de dados |

| **Pós Condição** | x |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF05
--------------------------------------------------
Titulo: O Sistema deve realizar a Validação de CNPJ
Descrição: Processo sistêmico de verificação matemática da integridade do Cadastro Nacional da Pessoa Jurídica (CNPJ) submetido, prevenindo a persistência de dados incorretos, erros de digitação e garantindo a consistência das entidades fiscais (clientes jurídicos e fornecedores)

| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Atendente |
| **Pré Condições** | RF01  |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|   1) Usuário Logado cadastra um novo cliente conforme RF01  |  |
|   2) Usuário informa o CPF/CNPJ do cliente |  |
|  | 3) Envia a informação para Brasil API: https://brasilapi.com.br/docs |
|  | 4) Valida CNPJ |
|  | 5) Retorna Validação  |
|  | 6) Permite salvar o registro de novo cliente |

| **Pós Condição** | Permissão para novo registro |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF06
--------------------------------------------------
Titulo: O Sistema deve permitir a Gestão de Orçamento
Descrição: Descreve a sequência de funções realizadas para o cadastro de um novo orçamento no sistema

| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | Solicitação de Orçamento |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|   1. Logado no sistema, acessa Cliente/Orçamento |  |
|  | 2. Lista todos os orçamentos em aberto para o cliente |
|  | 3. Exibe a opção de adicionar novo |
| 4. Clica em adicionar novo |  |
|  | 5. Exibe formulário para criação de orçamento: ID (único), Cliente, Veículo, Serviços, Produtos, Valores, Prazo de entrega |
| 6. Informa: Veículo, Serviços e quantidade, Produtos e quantidade |  |
|  | 7. Registra as informações de 6. na base de dados |

| **Pós Condição** | Não pode haver mais de um veículo por orçamento.  |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF07
--------------------------------------------------
Titulo: O Sistema deve permitir a Gestão de OS
Descrição: Processo estrutural que engloba a criação, consulta, atualização de escopo e cancelamento de uma Ordem de Serviço (OS). A OS atua como o Agregado Raiz (Aggregate Root), centralizando a relação entre o cliente, o veículo, o diagnóstico e os serviços/produtos aplicados.


| **Ator Principal** | Atendente ou Gerente de Operações |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | O Cliente e o Veículo devem estar previamente cadastrados na base de dados e o utilizador logado deve possuir permissões de acesso ao pátio ou à gestão de atendimento. |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Ator Principal acede ao módulo de Gestão de OS e aciona o comando "Nova Ordem de Serviço" |  |
| O Ator Principal seleciona o Cliente e o Veículo correspondente |  |
| O Ator Principal insere o relato inicial do problema (sintoma) reportado pelo cliente |  |
|  | O Sistema instancia a entidade OS com os dados fornecidos |
|  | O Sistema define o estado inicial da OS como "OS Recebida” |
|  | O Sistema persiste a OS na base de dados, gerando um número de identificação sequencial único |
|  | O Sistema apresenta o painel detalhado da OS gerada, permitindo a vinculação de serviços, produtos e a atribuição de um mecânico (RF26 ) |

### Fluxo Alternativo

#### Criação a partir de Orçamento Aprovado

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema interceta a transição de um Orçamento para o estado "Aprovado" |
|  | O Sistema executa os passos 4 a 7 de forma automatizada, herdando e migrando todo o escopo de peças, serviços e valores diretamente da entidade de Orçamento para a nova OS |

#### Cancelamento Administrativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Ator Principal aciona a opção "Cancelar OS" |  |
|  | O Sistema exige uma justificação textual |
|  | O Sistema altera o estado para "Cancelada" e emite eventos para libertar reservas de estoque pendentes (RF37 ) |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Ator Principal tenta adicionar um novo serviço ou produto a uma OS cujo estado é "OS Finalizada" ou "OS Entregue” |  |
|  | O Sistema bloqueia a mutação |
|  | O Sistema retorna a mensagem: "A modificação do escopo não é permitida para o estado atual da OS.*"* e impede a gravação |

| **Pós Condição** | A Ordem de Serviço encontra-se ativa, devidamente registada e pronta para transitar pelos ciclos operacionais do pátio (diagnóstico, aprovação, execução e entrega) |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF08
--------------------------------------------------
Titulo: O Sistema deve permitir a adição de múltiplas linhas de serviços em um orçamento
Descrição: Descreve a sequência de funções realizadas para adição de múltiplas linhas de serviço em um orçamento

| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | RF06  |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|   1. Após RF06  |  |
|  | 2. Lista serviços disponíveis para adição |
|  | 3. Permite a seleção de múltiplos registros |
| 4. Seleciona registros de serviços |  |
|  | 5. Remove serviço selecionado da lista de seleção |
|  | 6. Adiciona serviço ao orçamento |
| 7. Confirma a seleção de serviços |  |
|  | 8. Atualiza orçamento na base de dados |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| 4.1 Seleciona registro já adicionado ao orçamento |  |
|  | 4.2 Informa erro: serviço já adicionado ao orçamento |
|  |  |

| **Pós Condição** | O valor do serviço (sem produtos) é adicionado ao orçamento.  |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF09
--------------------------------------------------
Titulo: O Sistema deve permitir que um serviço tenha múltiplas linhas de produto. 
Descrição: Descreve a sequência de funções realizadas para adição de múltiplas linhas de produto em um serviço


| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | x |
| **Pré Condições** | Cadastro de Serviço, Cadastro de Produto |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|   1. Após RF04  |  |
|  | 2. Lista Produtos disponíveis para adição |
|  | 3. Permite a seleção de múltiplos registros |
| 4. Seleciona registros de produtos |  |
|  | 5. Adiciona produtos ao serviço |
|  | 6. Remove produtos selecionado da lista de seleção |
| 7. Confirma a seleção de produtos |  |
|  | 8. Atualiza serviço na base de dados (valor total) |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  |  |
|  |  |
|  |  |

| **Pós Condição** | O sistema separa preço do serviço, preço do produto, de preço total do serviço (serviço + produtos) |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF10
--------------------------------------------------
Titulo: O Sistema deve permitir adicionar linhas de produto dos serviços adicionados ao orçamento
Descrição: Descreve a sequência de funções realizadas para adição de múltiplas linhas de produto em um orçamento a partir dos produtos descritos em serviços

| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | x |
| **Pré Condições** | Produto Cadastrado, Serviço Cadastrado |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|   1. Após RF08  |  |
|  | 2. Busca em cada serviço adicionado, os produtos relacionados |
|  | 3. Retorna uma lista com todos os produtos relacionados a cada serviço |
|  | 4. Adiciona cada produto como uma linha de produto no orçamento: Produto, Quantidade, Preço Unitário, Preço total |

| **Pós Condição** | Adiciona valor dos produtos ao orçamento |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF11
--------------------------------------------------
Titulo: O Sistema deve permitir a adição de novas linhas de produto
Descrição: Descreve a sequência de funções realizadas para adição de múltiplas linhas de produto em um orçamento

| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | x |
| **Pré Condições** | Cadastro de Cliente, Cadastro de Produtos, Criação de Orçamento |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| 1. Após RF03  |  |
| 2. Acessa o orçamento |  |
|  | 3. Sistema exibe ação de adicionar produtos |
| 4. Clica em adicionar novo produto |  |
|  | 5. Lista Produtos disponíveis para adição |
|  | 6. Permite a seleção de múltiplos registros |
| 7. Seleciona registros de produtos |  |
|  | 8. Adiciona produtos ao orçamento: Produto, Quantidade, Preço Unitário, Preço Total |
|  | 9. Remove produtos selecionado da lista de seleção |
| 10. Confirma a seleção de produtos |  |
|  | 11. Atualiza orçamento na base de dados (valor total) |
|  |  |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  |  |
|  |  |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| 7.1 Seleciona um registro já adicionado |  |
|  | 7.2 Informa erro: Produto já adicionado ao orçamento |
|  |  |

| **Pós Condição** | Atualiza valor total do orçamento |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF12
--------------------------------------------------
Titulo: O Sistema deve calcular o preço total de um orçamento considerando todos os serviços e produtos do orçamento
Descrição: Descreve a sequência de funções realizadas para o cálculo dos valores dos serviços vinculados à um orçamento. 

| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | x |
| **Pré Condições** | Cadastro de Cliente, Veículo, Produtos e Serviços |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| Após RF06  |  |
|   1. Cliente informa serviços e produtos conforme o descrito em RF11 RF10 e RF08  |  |
|  | 2. Sistema verifica quantidade, preço unitário e calcula o preço total de cada linha |
|  | 3. Sistema calcula o preço total (soma do total de cada linha) ao final das linhas de orçamento.  |
|  | 4. Sistema recalcula sempre que um item for inserido ou removido das linhas de produtos/serviços.  |
| 5. Atendente Confirma Orçamento |  |
|  | 6. Orçamento é confirmado e produtos não podem ser adicionados ou removidos e o preço total fica fixo.  |
|  |  |
|  |  |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| 2.1 Produto adicionado não possui preço |  |
|  | 2.2 Retornar na confirmação do orçamento, mensagem de alerta: linha de produto x, não possui preço informado.  |
|  | 2.3 Prosseguir com a confirmação.  |

| **Pós Condição** | Orçamento Readonly, com valor total fixado.  |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF13
--------------------------------------------------
Titulo: O Sistema deve consultar a disponibilidade de produtos (peças e insumos)
Descrição: Descreve o processo pelo qual o sistema verifica o saldo disponível de um produto (peça ou insumo) no estoque, garantindo que o cálculo considere o Estoque Físico subtraído das Reservas ativas geradas por outras Ordens de Serviço.

| **Ator Principal** | Estoquista |
| --- | --- |
| **Atores Secundários** | Atendente, Mecânico |
| **Pré Condições** | RF03, Usuário autenticado no sistema |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|   1. O Ator Principal acessa a interface de busca de produtos ou adiciona um item em um Orçamento/OS |  |
| 2. O Ator Principal informa o identificador do produto (Nome, Código ou SKU) |  |
|  | 3. O Sistema localiza o produto no banco de dados |
|  | 4. O Sistema calcula o Estoque Disponível (Quantidade Física em Prateleira - Quantidade Reservada em OS Ativas) |
|  | 5. O Sistema retorna as informações do produto, exibindo o saldo disponível e liberando a seleção/alocação do item. |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| No **passo 2** do **fluxo principal**, o Ator Principal não informa um produto específico e aciona a listagem geral de estoque |  |
|  | O Sistema retorna uma tabela paginada com todos os produtos, exibindo para cada um: Estoque Físico, Quantidade Reservada e Estoque Disponível |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No **passo 3** do **fluxo principal**, o Sistema não localiza nenhum registro correspondente ao termo pesquisado |
|  | O Sistema exibe a mensagem de erro *"Produto não encontrado"* e retorna o foco para o campo de busca |

| **Pós Condição** | O Ator Principal obtém a visualização correta do saldo real e disponível do produto |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF14
--------------------------------------------------
Titulo: O Sistema deve calcular uma data prevista de entrega
Descrição: Processo de cálculo automático do prazo final para entrega do veículo ao cliente, baseado na soma do tempo de execução dos serviços, posição na fila de trabalho e tempo de espera por peças em falta.

| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | Sistema, Mecânico (?) |
| **Pré Condições** | O Orçamento/OS deve conter serviços parametrizados com estimativas de tempo. |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|   1. O Ator Principal aciona a funcionalidade de cálculo de prazo no Orçamento/OS |  |
|  | 2. O Sistema soma o tempo estimado de todos os serviços incluídos no escopo |
|  | 3. O Sistema cruza a disponibilidade das peças; caso haja insumos indisponíveis, identifica o prazo de entrega do fornecedor |
|  | 4. O Sistema avalia a Fila de Execução atual da oficina e a carga horária já comprometida |
|  | 5. O Sistema projeta a data de entrega, considerando apenas dias úteis |
|  | 6. O Sistema apresenta a data e hora previstas |
| 7. O Ator Principal confirma o prazo e o sistema regista a informação |  |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| 6.1 No passo 6 do fluxo principal, o Ator Principal opta por atribuir uma folga operacional |  |
| 6.2 O Ator Principal altera manualmente a data/hora apresentada |  |
|  | 6.3 O Sistema regista a nova data prevista e avança para a conclusão |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | 3.1 No passo 3 do fluxo principal, o Sistema identifica uma peça necessária sem quantidade em estoque e sem estimativa de entrega mapeada |
|  | 3.2 O Sistema bloqueia a geração automática |
|  | 3.3 O Sistema alerta o utilizador, indicando a peça bloqueante e solicitando a inserção manual do prazo ou a classificação da entrega como "Sob Consulta” |

| **Pós Condição** | 3.4 O Orçamento ou a Ordem de Serviço possui uma data de entrega formalizada e pronta para ser submetida à aprovação do cliente |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF15
--------------------------------------------------
Titulo: O Sistema deve gerar um pdf com todas as informações contidas no orçamento
Descrição: Processo de compilação e formatação dos dados comerciais (cliente, veículo, serviços, peças, totais e validade) num documento imutável (PDF), destinado à aprovação formal do cliente ou arquivo físico

| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | O orçamento deve estar instanciado na base de dados (status "Criado", "Aguardando Aprovação" ou "Aprovado"), o orçamento deve possuir um cliente e um veículo devidamente vinculados. |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Atendente acessa a interface de detalhes do Orçamento |  |
| O Atendente aciona o comando "Gerar PDF" (ou "Imprimir") |  |
|  | O Sistema compila a árvore de dados do orçamento: Cabeçalho (dados da oficina), Tomador (dados do cliente), Objeto (dados do veículo), Itens (produtos e serviços com suas quantidades e valores unitários), e Rodapé (subtotais, descontos, total geral, validade da proposta e termo de aceite) |
|  | O Sistema injeta os dados em um template HTML/CSS padronizado |
|  | O Sistema processa o *template* e o converte para o formato de arquivo PDF |
|  | O Sistema retorna o arquivo binário na resposta HTTP, acionando o download ou a visualização nativa no navegador do usuário |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | Durante a execução do envio de e-mail (RF16 ), o Sistema aciona o motor de PDF internamente |
|  | O Sistema executa os passos 3 a 5 do fluxo principal |
|  | Em vez de retornar para o usuário, o Sistema retém o binário em memória e o anexa à mensagem de correio eletrônico que será despachada |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 5 do fluxo principal, o processo de renderização esgota a memória disponível ou encontra uma falha na biblioteca de conversão |
|  | O Sistema interrompe a geração para evitar o travamento da aplicação |
|  | O Sistema retorna um erro HTTP 500 (Internal Server Error) tratado, exibindo a mensagem: "Não foi possível gerar o documento PDF no momento. Tente novamente mais tarde." e registra o *traceback* no log interno para a equipe de desenvolvimento |

| **Pós Condição** | Um documento digital consolidado e formatado é entregue ao usuário, preservando as informações comerciais exatas daquele momento no tempo. |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF16
--------------------------------------------------
Titulo: O Sistema deve poder enviar esse orçamemento via email. 
Descrição: Processo pelo qual o sistema envia o documento do orçamento (em formato PDF) diretamente para o endereço de correio eletrónico do cliente, registando a ação no histórico da oficina para efeitos de auditoria e acompanhamento comercial.

| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | X |
| **Pré Condições** | RF15, O orçamento tem de estar gerado e gravado na base de dados com um estado válido (ex: "Aguardando Aprovação"),, o cliente associado tem de possuir um endereço de correio eletrónico válido no seu perfil (ou este tem de ser fornecido no momento do envio). |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Atendente na tela de detalhes do Orçamento |  |
| O Atendente seleciona a opção "Enviar por E-mail" |  |
|  | O Sistema abre um *modal* (ou formulário) com o endereço de e-mail do cliente pré-preenchido, o assunto padronizado e uma mensagem de corpo base |
| O Atendente tem a opção de rever, adicionar novos destinatários (CC) ou personalizar a mensagem, e confirma o envio |  |
|  | O Sistema compila a mensagem, anexa o ficheiro PDF (RF15 ) e submete a tarefa de envio para processamento |
|  | O Sistema processa o envio através de um servidor SMTP |
|  | O Sistema regista no histórico do Orçamento a data, hora e o utilizador que efetuou a ação de envio |
|  | O Sistema apresenta uma mensagem de sucesso na tela do Atendente. |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No final do fluxo de geração do orçamento (RF06 / RF15 ), se o sistema estiver configurado para envio automático, ignora os passos 2 a 4 do fluxo principal, evitando ação do usuário |
|  | O Sistema submete imediatamente o e-mail em *background* e regista o histórico de forma automática |

### Fluxo de Exceção

#### Cliente sem e-mail registrado

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 3 do fluxo principal, o Sistema detecta que o campo de e-mail do cliente está vazio |
|  | O Sistema alerta o Atendente: *"O cliente não possui um endereço de e-mail registado"* |
|  | O Sistema exige o preenchimento manual do campo antes de permitir que o botão de envio seja acionado |

#### Erro de falha de comunicação

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 6 do fluxo principal, o serviço de e-mail não consegue estabelecer ligação ou as credenciais falham |
|  | O Sistema não bloqueia a interface do utilizador, mas regista o erro internamente (*log*) |
|  | O Sistema altera o estado de envio desse orçamento para "Falhado" e alerta o Atendente através de uma notificação visual para que tente efetuar o envio mais tarde. |

| **Pós Condição** | O cliente recebe o orçamento na sua caixa de entrada, e o sistema retém a prova temporal de que a proposta comercial foi remetida. |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF17
--------------------------------------------------
Titulo: O Email do orçamento deve conter uma ação que retorna a aprovação ou recusa do orçamento
Descrição: Processo que permite ao cliente interagir diretamente com o e-mail recebido, acionando ligações únicas e seguras para aprovar ou recusar o orçamento, atualizando o estado no sistema automaticamente sem a necessidade de autenticação

| **Ator Principal** | Cliente |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | O orçamento foi gerado e encontra-se no estado "Aguardando Aprovação",,, RF16  |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Cliente clica no botão "Aprovar Orçamento" presente no corpo do e-mail |  |
| O Cliente é redirecionado para a aplicação |  |
|  | O Sistema valida o token criptográfico contido no URL |
|  | O Sistema verifica a validade comercial do documento e se o estado atual permite transições |
|  | O Sistema altera o estado do Orçamento para "Aprovado" |
|  | O Sistema cria o objeto Ordem de Serviço com os dados do orçamento |
|  | O Sistema apresenta uma mensagem de confirmação na tela |
|  | O Sistema guarda o registo de auditoria (data, hora e IP do acionamento) |
|  | O Sistema emite um evento de notificação para a equipa de Atendimento |

### Fluxo Alternativo

#### Recusa do Orçamento

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| No passo 1, o Cliente clica no botão "Recusar" |  |
| O Cliente é redirecionado para a tela de recusa, sendo-lhe apresentado um campo opcional para justificar o motivo |  |
|  | O Sistema valida o *token* e atualiza o estado para "Não Aprovado" |
|  | O Sistema guarda o motivo de perda comercial e notifica a oficina |

#### Ausência de Resposta

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| No passo 1, o Cliente ignora o e-mail, não abrindo-o |  |
|  | O token criado pelo Sistema expira depois de 3 dias sem a aceitação ou recusa do cliente |
|  | O Sistema altera o estado do token para expirado e notifica a oficina |

 

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 4, o Sistema identifica que a proposta já foi previamente aprovada ou recusada |
|  | O Sistema ignora a tentativa de atualização e apresenta na tela o estado consolidado do documento |

| **Pós Condição** | O orçamento assume um estado terminal ou transitório definitivo, avançando o fluxo operacional da oficina sem intervenção humana no atendimento |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF18
--------------------------------------------------
Titulo: O Sistema deve gerar automaticamente uma OS com base na resposta do orçamento
Descrição: Processo de transição de estado no qual o sistema converte um Orçamento comercialmente aprovado numa Ordem de Serviço (OS) acionável, transferindo o escopo técnico e financeiro para a fila de execução do pátio da oficina

| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Cliente, Atendente |
| **Pré Condições** | RF17 |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema interceta o evento de aprovação do Orçamento |
|  | O Sistema instancia uma nova Ordem de Serviço |
|  | O Sistema vincula os identificadores do Cliente e do Veículo à nova OS |
|  | O Sistema vincula integralmente os Serviços, Produtos, Preços Congelados, Descontos e a Data Prevista de Entrega do documento do Orçamento |
|  | O Sistema define o estado inicial da OS como "OS Recebida" |
|  | O Sistema persiste a OS na base de dados |
|  | O Sistema regista o identificador da OS gerada no documento do Orçamento original para garantir rastreabilidade bidirecional |
|  | O Sistema posiciona a OS na "Fila de Execução" da oficina |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| Caso a geração automática falhe ou o fluxo de aprovação ocorra presencialmente, o Atendente se atenta aos detalhes do Orçamento Aprovado |  |
| O Atendente aciona ação "Gerar Ordem de Serviço" |  |
|  | O Sistema executa os passos 2 a 8 do fluxo principal de forma síncrona e devolve uma mensagem de sucesso na tela |

### Fluxo de Exceção

#### Duplicidade de OS para o mesmo Orçamento

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 2 do fluxo principal, o Sistema detceta que já existe uma OS ativa vinculada àquele identificador de Orçamento |
|  | O Sistema interrompe a execução imediatamente para evitar colisão e duplicação operacional |
|  | O Sistema emite um aviso sobre a não criação ao Atendente, mantendo a integridade da fila de execução |

#### Falha de Integridade Relacional

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 4, o Sistema identifica que um produto base do catálogo foi apagado fisicamente (*hard delete*) do banco de dados antes da conversão |
|  | O Sistema aborta a geração da OS |
|  | O Sistema aplica um **Rollback** na transação de banco de dados |
|  | O Sistema notifica o Atendente informando que o orçamento perdeu a consistência de dados e necessita de reprocessamento manual |

| **Pós Condição** | A oficina passa a ter uma Ordem de Serviço formalizada, estritamente parametrizada com os valores aprovados pelo cliente, pronta para a atribuição de um Mecânico e para a reserva sistémica das peças necessárias |
| --- | --- |]

==================================================

## REQUISITO FUNCIONAL: RF19
--------------------------------------------------
Titulo: O Sistema deve enviar por email um pdf da OS
Descrição: Processo de conversão dos dados estruturais de uma Ordem de Serviço (OS) ativa num documento PDF não editável, seguido do envio para o correio eletrónico do cliente para garantir o alinhamento técnico e legal sobre a manutenção

| **Ator Principal** | Atendente |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | RF18, Cliente com e-mail válido |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Atendente verifica os detalhes da Ordem de Serviço |  |
| O Atendente seleciona a opção "Enviar OS por E-mail" |  |
|  | O Sistema compila os dados técnicos e financeiros da OS e renderiza um ficheiro PDF em memória |
|  | O Sistema formata uma mensagem de e-mail padronizada e anexa o PDF gerado. |
|  | O Sistema despacha o e-mail via servidor SMTP |
|  | O Sistema regista no histórico da OS a data, hora e o utilizador responsável pelo envio |
|  | O Sistema apresenta uma notificação de sucesso na interface |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No instante em que o sistema conclui a geração da OS (RF18 ), aciona automaticamente os passos 3 a 6 do fluxo principal em backgound, dispensando a intervenção do Atendente. |

### Fluxo de Exceção

#### Ausência de E-mail de Destino

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 2, o Sistema identifica que o cadastro do cliente não possui um endereço de e-mail válido |
|  | O Sistema bloqueia a renderização e o envio |
|  | O Sistema alerta o Atendente para a necessidade de atualizar o registo do cliente antes de prosseguir |

#### Indisponibilidade do serviço SMTP

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 5, ocorre uma falha na ligação com o servidor de correio eletrônico |
|  | O Sistema marca o envio como "Pendente" ou "Falhado" no histórico de notificações |
|  | O Sistema informa o Atendente do erro, permitindo a tentativa manual posterior, sem bloquear o fluxo operacional da OS |

| **Pós Condição** | O cliente recebe uma cópia formal e imutável da Ordem de Serviço, e o sistema rastreia a auditoria da comunicação |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF20
--------------------------------------------------
Titulo: O Sistema deve permitir a gestão de Reserva
Descrição: Processo que assegura a alocação sistêmica de produtos (peças e insumos) para uma Ordem de Serviço específica, prevenindo a ruptura de estoque e garantindo a disponibilidade dos materiais até a baixa física no estoque

| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Estoquista, Atendente |
| **Pré Condições** | RF03, A Ordem de Serviço deve estar instanciada e num estado que exija separação de peças (ex: "Em Execução" ou "Aprovada"). |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema identifica a aprovação de uma OS ou a adição de um novo produto ao escopo técnico |
|  | O Sistema consulta o *Estoque Disponível* do produto (RF13) |
|  | O Sistema valida que há saldo suficiente para suprir a demanda da OS |
|  | O Sistema instancia um registro de "Reserva", vinculando o identificador do Produto, a Quantidade exigida e o identificador da OS |
|  | O Sistema persiste a Reserva no banco de dados |
|  | O Sistema atualiza o Estoque Disponível visual, bloqueando o consumo dessa quantidade por outras ordens de serviço (o Estoque Físico permanece intacto até a retirada real) |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| A OS é cancelada ou uma peça é removida do escopo do serviço pelo Mecânico |  |
|  | O Sistema identifica o registro de Reserva correspondente ativo |
|  | O Sistema inativa ou exclui a Reserva |
|  | O Sistema devolve automaticamente a quantidade ao Estoque Disponível |

### Fluxo de Exceção

#### Estoque Insuficiente para Reserva

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 3 do fluxo principal, o Sistema identifica que o saldo disponível é menor que a quantidade requisitada (race condition). |
|  | O Sistema bloqueia a criação da Reserva |
|  | O Sistema marca o item na OS como "Pendente de Estoque” |
|  | O Sistema aciona o gatilho de necessidade de compra e alerta o Estoquista/Atendente |

| **Pós Condição** | A peça ou insumo fica bloqueado logicamente para a OS solicitante, protegendo a operação do mecânico e garantindo a integridade da fila de execução contra falta de peças prometidas |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF21
--------------------------------------------------
Titulo: O Sistema deve permitir a gestão de Solicitação de Compra
Descrição: Processo que abrange a criação, visualização, edição e cancelamento de pedidos internos de aquisição de produtos   devido à indisponibilidade de estoque para uma Ordem de Serviço ou ao atingimento do nível de estoque mínimo de segurança

| **Ator Principal** | Estoquista ou Atendente |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | RF03, O usuário deve possuir permissões de acesso ao módulo de compras ou estoque. |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Ator Principal acessa a interface de Solicitações de Compra |  |
| O Ator Principal pressiona a opção para criar uma nova solicitação |  |
| O Ator Principal informa o produto desejado, a quantidade necessária, o prazo limite para chegada e, opcionalmente, o identificador da OS que gerou a demanda |  |
|  | O Sistema valida a existência do produto e a coerência dos dados informados |
|  | O Sistema grava a solicitação de compra no banco de dados com o estado inicial "Pendente" |
|  | O Sistema atualiza a listagem e exibe uma mensagem de sucesso |

### Fluxo Alternativo

Nenhum cenário disponível.

|  |  |
| --- | --- |
|  |  |
|  |  |
|  |  |
|  |  |
|  |  |

### Fluxo de Exceção

#### Solicitação Pendente Duplicada

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 4 do fluxo principal, o Sistema detecta que já existe uma Solicitação de Compra com o estado "Pendente" para o mesmo produto e vinculado à mesma OS |
|  | O Sistema interrompe a criação do novo registro |
|  | O Sistema alerta o Ator Principal sobre a solicitação existente e sugere a edição da atual para consolidar e somar as quantidades, evitando múltiplas frentes de compra para o mesmo item |

| **Pós Condição** | A oficina consolida uma demanda formal e registrada de suprimentos, alimentando a fila de compras do setor responsável para que seja cotada junto aos fornecedores e convertida em um Pedido de Compra |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF22
--------------------------------------------------
Titulo: O Sistema deve pesquisar se há recebimento gerado para os produtos não disponíveis
Descrição: Processo sistêmico que verifica a existência de entradas programadas no estoque. Quando uma peça não possui saldo imediato para atender a uma Ordem de Serviço, o sistema consulta se já existe um Pedido de Compra aprovado ou um Recebimento em trânsito, evitando compras duplicadas e fornecendo um prazo de chegada ao Atendente

| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Atendente, Estoquista |
| **Pré Condições** | RF13 ou RF20 , O módulo de Gestão de Fornecedores/Compras deve estar devidamente integrado e operacional |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema detecta a falta de saldo para alocação de um produto |
|  | O Sistema intercepta o evento de falta e consulta a tabela de "Pedidos de Compra" (ou "Recebimentos") |
|  | O Sistema procura por registos com estado "Em Trânsito" ou "Aguardando Entrega" que contenham o produto faltante |
|  | O Sistema localiza um carregamento previsto e soma a quantidade a caminho |
|  | O Sistema valida que a quantidade a caminho é suficiente para cobrir a demanda pendente da OS |
|  | O Sistema extrai a "Data Prevista de Entrega" do fornecedor atrelada a este recebimento |
|  | O Sistema apresenta um aviso não bloqueante na interface da OS: *"Produto sem stock físico, mas com [Quantidade] unidades em trânsito. Previsão de chegada: [Data]"* |
|  | O Sistema permite que o Atendente adicione a peça à OS sob regime de "Em Análise", afetando o cálculo final de entrega do veículo (RF14 ) |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 5 do fluxo principal, o Sistema detecta que existe um carregamento em trânsito, mas a quantidade a chegar já está comprometida com outras reservas ou não cobre o total exigido |
|  | O Sistema informa o saldo em trânsito e a sua limitação |
|  | O Sistema aciona imediatamente o fluxo de Solicitação de Compra (RF23 ) referente apenas à diferença que ficou a descoberto |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 3, o Sistema verifica que não há nenhum Pedido de Compra em aberto para aquele produto. |
|  | O Sistema sinaliza a peça com o estado crítico de indisponibilidade total e sem previsão |
|  | O Sistema bloqueia a promessa de prazo de entrega da OS e aciona obrigatoriamente a geração de uma nova solicitação de compra |

| **Pós Condição** | A equipe de Atendimento obtém visibilidade total sobre a logística, evitando a realização de compras redundantes (desperdício de tempo e dinehiro) e garante uma comunicação transparente de prazos com o cliente |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF23
--------------------------------------------------
Titulo: Geração Automática de Solicitação de Compra por Ruptura de Estoque
Descrição: Processo automatizado em que o sistema cria uma solicitação interna de compra de um item (peça ou insumo) quando identifica que não há saldo físico disponível e também não há registros de recebimentos programados ou em trânsito para suprir a demanda de uma Ordem de Serviço


| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Estoquista |
| **Pré Condições** | RF13  retornou saldo insuficiente para a OS, A consulta de recebimentos pendentes (RF22 ) confirmou a inexistência de pedidos em trânsito capazes de suprir a falta |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema detecta a falta de saldo de um produto e a ausência de recebimentos futuros programados para o item |
|  | O Sistema calcula a quantidade exata em falta para atender ao escopo da Ordem de Serviço |
|  | O Sistema gera automaticamente uma nova Solicitação de Compra (RF21 ) |
|  | O Sistema preenche a solicitação com o identificador do produto, a quantidade necessária calculada,  o recebimento criado é definido como estado “Pendente” |
|  | O Sistema associa a solicitação à lista de pendências da oficina |
|  | O Sistema altera o estado da Ordem de Serviço para "Aguardando Compra” |
|  | O Sistema emite um alerta ou notificação interna para o Estoquista (ou painel de compras) sinalizando a nova demanda crítica |

### Fluxo Alternativo

Nenhum cenário disponível.

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 3, o Sistema tenta gerar a solicitação, mas identifica que todos os fornecedores homologados para o produto estão inativos |
|  | O Sistema suspende a criação da solicitação de compra padrão |
|  | O Sistema gera um alerta para o Estoquista e Gestor da oficina providenciar a substituição do item ou cadastro de novo fornecedor |

| **Pós Condição** | A demanda de compra fica formalizada de forma automática no Back-Office - até por isso não há um fluxo alternativo -, e a Ordem de Serviço fica travada no pátio com o status correto de dependência de peça, protegendo a equipe técnica de iniciar um trabalho que **não poderá ser concluído** |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF24
--------------------------------------------------
Titulo: Geração Automática de Recebimento de Pedido de Compra
Descrição: Processo automatizado em que o sistema cria um registro de Recebimento (ou documento de conferência física de entrada) com status "Pendente" no momento em que um Pedido de Compra formal é aprovado e enviado ao fornecedor, preparando o Back-Office para a futura validação e conferência da nota fiscal e dos itens físicos

| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Estoquista |
| **Pré Condições** | O Pedido de Compra, Os produtos (RF03 ) listados no pedido devem possuir vínculo com um fornecedor ativo (RF29 ) |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema intercepta o evento de aprovação de um Pedido de Compra |
|  | O Sistema instancia um novo registro na tabela de "Recebimento” |
|  | O Sistema vincula o identificador do Pedido de Compra de origem e o identificador do Fornecedor ao novo registro de Recebimento |
|  | O Sistema duplica o grafo de itens do Pedido de Compra para a estrutura do Recebimento, inicializando o campo QUANTIDADE RECEBIDA com o valor zero |
|  | O Sistema define o status inicial do Recebimento como "Pendente" |
|  | O Sistema calcula e insere a "Data Prevista de Entrega" com base no prazo informado pelo fornecedor (RF22 ) |
|  | O Sistema persiste o registro no banco de dados e atualiza o painel do almoxarifado |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| Durante a chegada física dos produtos, o Estoquista identifica que o fornecedor entregou apenas uma parte do Pedido de Compra |  |
| O Estoquista preenche as quantidades que de fato chegaram e aciona a gravação |  |
|  | O Sistema efetua a baixa parcial, atualiza o estoque físico das peças que chegaram e gera automaticamente um *segundo* registro de Recebimento, com status "Aguardando Entrega", contendo apenas o saldo residual pendente do pedido original |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No momento da geração automática, o Sistema identifica que um produto contido no Pedido de Compra foi marcado como inativo ou excluído do catálogo geral do sistema |
|  | O Sistema aborta a geração do Recebimento e aplica rollback na transação |
|  | O Sistema emite um alerta de erro para o usuário apontando a inatividade ou ausência do produto. |

| **Pós Condição** | O Back-Office da oficina passa a contar com um documento de expectativa de estoque, mapeando as peças em trânsito para fornecer dados previsíveis para a Gestão de OS (RF22) e aguardando a conferência física final do Almoxarifado |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF25
--------------------------------------------------
Titulo: Geração Automática de Reserva de Estoque via OS
Descrição: Processo que intercepta a adição de um produto (peça ou insumo) ao escopo técnico de uma Ordem de Serviço (OS) e cria automaticamente um bloqueio lógico (reserva) dessa quantidade no estoque, prevenindo concorrência com outras ordens de serviço


| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Atendente, Mecânico |
| **Pré Condições** | RF13, a Ordem de Serviço deve estar ativa |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Ator Secundário adiciona um produto ao escopo de produtos da OS |  |
|  | O Sistema persiste o item na base de dados vinculado à OS |
|  | O Sistema intercepta o evento de gravação do novo item |
|  | O Sistema deduz logicamente a quantidade do Estoque Disponível do produto |
|  | O Sistema gera um registro formal de Reserva (RF20 ) vinculando o Produto, a Quantidade e a OS |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Ator Secundário edita a quantidade de um produto já existente na OS |  |
|  | O Sistema calcula a diferença entre a quantidade antiga e a nova |
|  | O Sistema atualiza o registro de Reserva existente com o novo valor e recalcula o Estoque Disponível |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 4 do fluxo principal, o Sistema identifica que o Estoque Disponível é insuficiente |
|  | O Sistema bloqueia a criação da reserva |
|  | O Sistema exibe em tela ao usuário a opção de Solicitação de Compra para a quantidade faltante (RF23 ) |

| **Pós Condição** | A quantidade do produto fica imobilizada logicamente para uso exclusivo daquela Ordem de Serviço até o momento da retirada física no almoxarifado |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF26
--------------------------------------------------
Titulo: Atribuição de Mecânico Responsável à OS
Descrição: Processo que viabiliza a vinculação de um mecânico específico a uma Ordem de Serviço, definindo formalmente a responsabilidade pela execução dos serviços e pelo diagnóstico do veículo

### **Fluxo Principal**

| **Ator Principal** | Atendente, Gestor da Oficina |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | A Ordem de Serviço deve estar cadastrada e no estado “Recebida”, O mecânico a ser atribuído deve estar devidamente cadastrado no sistema, com contrato ativo e sem impedimentos operacionais |

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Ator Principal acessa a interface de detalhes de uma Ordem de Serviço específica |  |
| O Ator Principal presiona a opção "Atribuir Responsável” |  |
|  | O Sistema apresenta uma listagem filtrada de mecânicos disponíveis |
| O Ator Principal seleciona o mecânico desejado e confirma a operação |  |
|  | O Sistema valida o estado atual da OS e a elegibilidade do profissional |
|  | O Sistema vincula o identificador do Mecânico à Ordem de Serviço |
|  | O Sistema altera automaticamente o estado da OS para o próximo estágio operacional (RF27) |
|  | O Sistema registra a ação no histórico de auditoria da OS (data, hora e usuário autor) |
|  | O Sistema exibe uma notificação de sucesso na tela |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | A OS já possui um responsável, mas o profissional precisa ser substituído |
| O Ator Principal aciona "Alterar Responsável” |  |
| O Ator Principal seleciona o novo mecânico e justifica obrigatoriamente a troca através de um campo de texto **não obrigatório** |  |
|  | O Sistema atualiza o vínculo para o novo ID de mecânico, mantém o status atual da OS intacto e grava o motivo da substituição no histórico |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 5 do fluxo principal, o Sistema identifica que o mecânico selecionado foi desativado no RH ou possui uma restrição administrativa interna |
|  | O Sistema bloqueia a vinculação |
|  | O Sistema apresenta a mensagem de erro *"Não é possível atribuir a OS a um profissional inativo"* e retorna à tela de seleção |

| **Pós Condição** | A Ordem de Serviço possui um executor definido, viabilizando o início das atividades técnicas no pátio e o correto direcionamento da fila de tarefas do profissional |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF27
--------------------------------------------------
Titulo: O Sistema deve alterar o status da OS para “Em Diagnóstico” após a atribuição de um responsável
Descrição: Processo sistêmico automatizado de transição de estado da Ordem de Serviço (OS). Garante que, assim que um mecânico for alocado, a OS saia da fila de espera inicial ("OS Recebida" ou "Pendente") e avance para a etapa de diagnóstico, refletindo com exatidão o andamento operacional no pátio da oficina


| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Atendente, Gestor |
| **Pré Condições** | A Ordem de Serviço deve encontrar-se num estado inicial compatível com a transição: "Recebida", RF26  |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema intercepta a conclusão da vinculação de um mecânico à OS |
|  | O Sistema verifica se o estado atual da OS permite a transição para a próxima fase |
|  | O Sistema altera o campo de estado da OS para "Em Diagnóstico” |
|  | O Sistema persiste a alteração no banco de dados |
|  | O Sistema regista a transição na tabela de histórico de auditoria (Log), incluindo o usuário, a data e hora exatas do evento |
|  | O Sistema atualiza o painel de controlo (Kanban/Lista) da oficina em tempo real |

### Fluxo Alternativo

Nenhum cenário disponível.

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  |  |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 2, o Sistema identifica que a OS já se encontra no estado "Em Execução" ou "Finalizada" devido a uma atualização manual prévia ou concorrência |
|  | O Sistema aborta a transição automática para evitar retrocesso operacional |
|  | O Sistema regista um aviso no log interno indicando a tentativa de sobreposição de estados |

| **Pós Condição** | A Ordem de Serviço fica corretamente sinalizada no sistema como "Em Diagnóstico", libertando a interface para que o mecânico possa interagir com a OS e inserir as anotações técnicas necessárias |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF28
--------------------------------------------------
Titulo: O Sistema deve permitir a atribuição de uma prioridade para a OS
Descrição: Processo que viabiliza a definição e alteração do nível de urgência de uma Ordem de Serviço (OS). A prioridade influencia diretamente a ordenação automática da fila de execução no pátio e a visualização dos mecânicos, garantindo que veículos críticos (como frotas ou retornos de garantia) sejam atendidos preferencialmente

| **Ator Principal** | Atendente, Gestor da Oficina |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | RF07 , O usuário deve possuir permissão para gerenciar o fluxo operacional da oficina |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Ator Principal acessa os detalhes ou o painel delistagem da Ordem de Serviço |  |
| O Ator Principal seleciona a opção "Definir Prioridade” |  |
|  | O Sistema apresenta as opções de níveis de prioridade parametrizadas (ex: Baixa, Média, Alta, Crítica/Garantia) |
| O Ator Principal escolhe o nível desejado e confirma a atribuição |  |
|  | O Sistema valida que a OS está ativa e salva o novo nível de prioridade no banco de dados |
|  | O Sistema dispara um gatilho de reordenação automática na fila de execução do pátio |
|  | O Sistema registra o evento no histórico de auditoria da OS, detalhando o nível escolhido, data, hora e o usuário responsável |
|  | O Sistema exibe visualmente a nova prioridade através de sinalizadores coloridos na interface |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | Durante a criação da OS ou do orçamento, o sistema identifica que o tipo de **atendimento foi classificado como "Retorno de Garantia" ou "Cliente VIP/Frota”** |
|  | O Sistema ignora a seleção manual e atribui automaticamente a prioridade "Crítica” |
|  | O Sistema executa os passos 5 a 8 do fluxo principal |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 5, o Sistema detecta que a OS foi finalizada (RF33 ) ou paga (RF40 ) |
|  | O Sistema bloqueia a alteração |
|  | O Sistema retorna o erro HTTP 422 (Unprocessable Entity) informando que não é permitido alterar dados de uma Ordem de Serviço encerrada |

| **Pós Condição** | A Ordem de Serviço é atualizada com o seu novo peso operacional, reposicionando o veículo na fila de trabalho e otimizando o fluxo logístico dos mecânicos |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF29
--------------------------------------------------
Titulo: O Sistema deve permitir a gestão de fornecedor
Descrição: Processo que engloba a criação, consulta, atualização e desativação de registros de fornecedores (empresas ou autônomos que suprem a oficina com peças, insumos ou serviços terceirizados como retíficas). A manutenção desses dados garante a rastreabilidade nas compras (@RF21 ) e o vínculo correto no recebimento de mercadorias (@RF24 )

| **Ator Principal** | Atendente, Estoquista, Gestor |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | O usuário deve estar autenticado e possuir nível de permissão administrativo ou de gestão de estoque |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Ator Principal acessa o módulo de cadastros e seleciona a opção "Gestão de Fornecedores” |  |
| O Ator Principal aciona o comando "Novo Fornecedor” |  |
| O Ator Principal preenche os dados obrigatórios: Razão Social, Nome Fantasia, Endereço Completo, Telefone, E-mail de contato comercial e Tempo de Lead Time padrão (prazo médio de entrega) |  |
|  | Caso informado, o Sistema valida a estrutura dos campos e executa um algoritmo de validação de integridade do CNPJ/CPF |
|  | Caso informado, o Sistema valida em API externa a veracidade do CNPJ/CPF |
|  | O Sistema verifica se a identificação fiscal informada já existe na base de dados para evitar duplicidade |
|  | O Sistema persiste o registro com o status "Ativo” |
|  | O Sistema apresenta uma mensagem de sucesso na interface |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Ator Principal localiza um fornecedor existente através da barra de pesquisa e aciona o comando "Editar” |  |
| O Ator Principal modifica as informações necessárias clica em "Salvar” |  |
|  | O Sistema valida as alterações e atualiza o registro no banco de dados, registrando o histórico de modificação |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 4 do fluxo principal, o Sistema detecta que o CNPJ ou CPF informado não está registrado na API de consulta |
|  | O Sistema bloqueia a submissão do formulário |
|  | O Sistema exibe o erro HTTP 422 (Unprocessable Entity) e destaca visualmente o campo com a mensagem: *"CNPJ/CPF inválido"* |
|  | No passo 5 do fluxo principal, o Sistema identifica que o CNPJ/CPF inserido já consta em outro registro do banco de dados |
|  | O Sistema impede a gravação para evitar colisão de chaves exclusivas |
|  | O Sistema exibe um alerta informando que o fornecedor já possui cadastro ativo ou inativo no sistema |

| **Pós Condição** | O fornecedor fica disponível na base de dados, permitindo sua vinculação direta a catálogos de produtos, cotações, solicitações de compras de peças e fluxos logísticos de recebimento |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF30
--------------------------------------------------
titulo: O Sistema deve permitir a atualização do estoque
descrição: Processo que viabiliza a modificação manual ou automatizada da quantidade física de produtos (peças e insumos) armazenados no almoxarifado, cobrindo inventários rotativos, correções de perdas, quebras ou entradas por devolução

| **Ator Principal** | Estoquista, Gestor |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | RF03 , O usuário deve possuir nível de acesso restrito ao perfil de almoxarifado ou gerência |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Ator Principal acessa a ficha técnica do Produto e aciona a opção "Atualizar Estoque / Ajustar Saldo” |  |
| O Ator Principal informa o tipo de movimentação (Entrada Manual ou Saída Manual), a quantidade movimentada e a justificativa (ex: Inventário, Perda por Avaria, Devolução de Cliente) |  |
|  | O Sistema valida se os dados numéricos informados são coerentes |
|  | O Sistema recalcula a quantidade física do produto aplicando a operação matemática no banco de dados |
|  | O Sistema recalcula o saldo disponível do produto (Estoque Físico Novo - Reservas Ativas) |
|  | O Sistema grava um registro cronológico na tabela de movimentação de estoque, contendo o saldo anterior, o saldo atual, o tipo, o motivo, a data/hora e o identificador do usuário |
|  | O Sistema apresenta uma notificação de sucesso e atualiza a interface |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | Durante a finalização do processo de recebimento de mercadorias (RF24 ), o Sistema identifica a nota fiscal de entrada aprovada pelo fornecedor |
|  | O Sistema executa os passos 4, 5 e 6 do fluxo principal de forma embutida, utilizando o motivo "Entrada por Nota Fiscal de Compra" e dispensando a intervenção manual na ficha do produto |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| No passo 4, o Ator Principal tenta realizar um ajuste de saída cuja quantidade resulta num estoque físico menor que zero |  |
|  | O Sistema bloqueia a transação imediatamente |
|  | O Sistema retorna o erro HTTP 422 (Unprocessable Entity) informando que o estoque físico de um item tangível não pode assumir valores negativos |
|  | No passo 4, o Sistema detecta que o saldo do produto foi modificado por outro terminal de trabalho ou processo assíncrono exatamente após o carregamento da tela atual |
|  | O Sistema aborta a operação de gravação e desfaz as alterações em memória (rollback) |
|  | O Sistema emite um alerta **instruindo o usuário a recarregar a página para visualizar o saldo real antes de computar o ajuste** |

| **Pós Condição** | A quantidade física e o saldo disponível do item são atualizados com precisão na base de dados, garantindo que consultas subsequentes (RF13 ) reflitam a realidade física do almoxarifado |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF31
--------------------------------------------------
Titulo: O Sistema deve alocar uma OS com status de Aguardando Aprovação, com aprovação vínculada, para uma fila de execução
Descrição: Processo sistémico automático que identifica a transição de um Orçamento/OS para o estado "Aprovado" (@RF17 ) e posiciona esta Ordem de Serviço na fila de trabalho ativa do pátio da oficina, respeitando critérios operacionais e de prioridade.


| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Atendente |
| **Pré Condições** | A OS deve possuir um vínculo de aprovação rastreável (RF17 ) e o estado atual da OS deve ser "Aguardando Aprovação". |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema interceta o evento de consolidação da aprovação vinculada à OS |
|  | O Sistema altera o status da OS para "OS Recebida" (ou "Aguardando Início") |
|  | O Sistema consulta o nível de prioridade atribuído à OS (RF28 ) |
|  | O Sistema insere a OS na Fila de Execução Geral da oficina |
|  | O Sistema ordena a fila colocando a nova OS na posição correta (considerando a prioridade definida: Crítica vai para o topo, Baixa vai para o final) |
|  | O Sistema atualiza em tempo real o painel visual (Kanban) dos mecânicos na oficina |
|  | O Sistema regista a entrada na fila e a transição no histórico de auditoria da OS |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 1, o Sistema detecta uma tentativa de alteração de estado para a fila de execução, mas não localiza o registro do vínculo/assinatura de aprovação do cliente ou atendente |
|  | O Sistema aborta a transição e aplica rollback |
|  | O Sistema retorna o erro HTTP 422 informando que a alocação na fila de trabalho exige uma aprovação previamente auditada e vinculada |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 2, o Sistema identifica que a OS possui itens com estado "Crítico - Sem Fornecedor" (RF23 ) |
|  | O Sistema impede o posicionamento na fila ativa de execução para não poluir o pátio com um carro que não pode ser reparado |
|  | O Sistema move a OS para uma fila de exceção chamada "Aguardando Suprimentos" e emite um alerta para o Gestor |

| **Pós Condição** | A Ordem de Serviço encontra-se formalmente alocada na fila de execução da oficina, visível para a equipe técnica dar início ao atendimento físico (RF32 ) |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF32
--------------------------------------------------
Titulo: O Sistema deve permitir informar o início de atendimento
Descrição: Processo no qual o mecânico responsável sinaliza formalmente no sistema o início das atividades operacionais e técnicas no veículo. Esta ação altera o status da Ordem de Serviço (OS), retira o veículo da fila de espera visual e inicia a contagem de tempo real de pátio (SLA de execução)

| **Ator Principal** | Mecânico |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | A Ordem de Serviço deve estar no status "Aguardando Início" ou "Em Diagnóstico” (RF27 ), A OS deve possuir um mecânico atribuído (RF26 ), O usuário logado deve ser o próprio mecânico responsável pela OS ou um Gestor com permissões de sobreposição. |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Mecânico acessa o seu painel de trabalho |  |
| O Mecânico localiza a OS prioritária e aciona o comando "Iniciar Atendimento” |  |
|  | O Sistema valida se o mecânico logado tem permissão para iniciar aquela OS específica |
|  | O Sistema verifica se não há impedimentos sistêmicos |
|  | O Sistema registra um *timestamp* (data e hora exatas) de "Início de Execução" na tabela de apontamento de horas |
|  | O Sistema altera o status da OS para "Em Execução" |
|  | O Sistema atualiza o painel visual da oficina, movendo o card da OS para a coluna correspondente |
|  | O Sistema registra o evento no histórico de auditoria |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | Se a OS já havia sido iniciada anteriormente, mas foi identificado a necessidade de reparos adicionais. Portanto, a OS está com o status de “Aguardando Aprovação” |
|  | Ao acionar "Iniciar Atendimento", o Sistema não altera o status para a primeira execução, mas sim registra um novo bloco de *timestamp* de "Retomada" e volta o status para "Em Execução", garantindo que o tempo pausado não prejudique a métrica de produtividade do mecânico |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 4, o Sistema verifica que a OS possui peças marcadas como "Aguardando Compra" (RF23 ) |
|  | O Sistema bloqueia o início da execução |
|  | O Sistema alerta o Mecânico de que o atendimento não pode ser iniciado porque o escopo técnico depende de insumos que ainda não chegaram ao almoxarifado |

| **Pós Condição** | O relógio de produtividade do mecânico é iniciado, a oficina passa a ter visibilidade real de que o carro está sendo manipulado, e o cálculo de prazo de entrega começa a consumir a sua margem de segurança |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF33
--------------------------------------------------
Titulo: O Sistema deve permitir informar a finalização de um atendimento
Descrição: Processo que permite ao mecânico responsável ou ao gestor encerrar formalmente o ciclo técnico de trabalho em um veículo. A finalização trava a contagem de tempo produtivo, consolida os custos de mão de obra (se aplicável), e altera o status da OS, disponibilizando o veículo para o controle de qualidade ou para o faturamento comercial

| **Ator Principal** | Mecânico |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | A Ordem de Serviço deve estar no status "Em Execução" (RF32 ), o usuário logado deve ter as permissões adequadas para encerrar a OS. |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Mecânico acessa o seu painel e localiza a OS que está "Em Execução” |  |
| O Mecânico aciona a ação "Finalizar Atendimento" (ou "Concluir OS") |  |
|  | O Sistema abre um *modal* solicitando a confirmação da conclusão de todos os itens do escopo técnico e a inserção opcional de um parecer final/laudo técnico |
| O Mecânico confirma a operação |  |
|  | O Sistema estampa o *timestamp* de fim (`ended_at`) na sessão de trabalho atual (RF32 ), encerrando a contagem de horas do profissional |
|  | O Sistema altera o status da Ordem de Serviço para "Aguardando Faturamento" (ou "Aguardando Controle de Qualidade", dependendo do fluxo da oficina) |
|  | Sistema bloqueia a adição de novos produtos ou serviços ao escopo da OS |
|  | O Sistema registra o evento e a transição no histórico de auditoria |
|  | O Sistema remove o card do painel de execução e emite um evento interno notificando o setor de atendimento de que o veículo está pronto |

### Fluxo Alternativo

Não identificado.

|  |  |
| --- | --- |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 4, o Sistema verifica se há itens marcados como "Estoque Reservado" (RF25 ) que ainda não sofreram a baixa física definitiva do almoxarifado |
|  | O Sistema impede a finalização técnica da OS |
|  | O Sistema alerta o Mecânico e o Almoxarifado para que as peças sejam devidamente entregues e baixadas antes do encerramento sistêmico, garantindo a rastreabilidade do estoque |

| **Pós Condição** | A oficina encerra a responsabilidade técnica sobre o veículo. O custo de horas trabalhadas é consolidado, e o fluxo avança estritamente para a camada comercial (cobrança e entrega ao cliente) |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF34
--------------------------------------------------
Titulo: O Sistema deve permitir a solicitação de uma retirada de estoque
Descrição: Processo que formaliza a transição entre a reserva lógica de um produto (peça ou insumo) e a sua necessidade física imediata no pátio da oficina. A solicitação notifica o almoxarifado (Back-Office) para separar os itens e disponibilizá-los para o mecânico executar o serviço.

| **Ator Principal** | Mecânico |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | A Ordem de Serviço deve estar em um status que permita a execução técnica (ex: "Em Execução" ou "Aguardando Início") e os produtos solicitados devem estar vinculados à OS e possuir uma Reserva de Estoque ativa (RF25 ). |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Mecânico acessa o painel de execução da Ordem de Serviç |  |
| O Mecânico aciona o comando "Solicitar Peças/Insumos" para os itens que irá utilizar |  |
|  | O Sistema valida se os itens solicitados possuem reservas lógicas garantidas no estoque |
|  | O Sistema instancia um documento interno de "Solicitação de Retirada", contendo o identificador da OS, o Mecânico solicitante e a lista de itens com suas respectivas quantidades |
|  | O Sistema altera o status dos itens dentro da OS de "Estoque Reservado" para "Aguardando Separação” |
|  | O Sistema atualiza o painel de controle do Almoxarifado, posicionando a solicitação na fila de trabalho do Estoquista |
|  | O Sistema registra a ação no histórico da OS |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Mecânico decide que não precisa de todas as peças de uma vez (ex: peças do motor no primeiro dia, peças de suspensão no segundo) |  |
| No passo 2, o Mecânico seleciona apenas os itens específicos que deseja retirar no momento |  |
|  | O Sistema gera a Solicitação de Retirada apenas para os itens marcados, mantendo o restante no status original ("Estoque Reservado") |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 3, o Sistema detecta que o Mecânico tentou adicionar e solicitar uma peça de balcão que não passou pela aprovação do orçamento nem gerou reserva sistêmica |
|  | O Sistema bloqueia a emissão da solicitação para esse item |
|  | O Sistema emite um alerta de segurança: *"O item não possui aprovação comercial ou reserva vinculada a esta OS."* e instrui o Mecânico a solicitar um diagnóstico/orçamento complementar |

| **Pós Condição** | A equipe do Almoxarifado recebe uma ordem formal de separação (picking) de peças, lastreada por uma Ordem de Serviço auditável, impedindo "saídas de boca" e protegendo a oficina contra desvios de inventário. |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF35
--------------------------------------------------
Titulo: O Sistema deve notificar o estoquista de toda solicitação de retirada
Descrição: Processo automatizado de comunicação interna que alerta a equipa do almoxarifado assim que um mecânico emite uma Solicitação de Retirada de peças para o pátio, garantindo o tempo de resposta do Back-Office à produção.

| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Estoquista |
| **Pré Condições** | A Solicitação de Retirada (RF34 ) foi criada e validada com sucesso na base de dados, o serviço de mensageria em tempo real da aplicação encontra-se operacional. |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema escuta o evento de domínio referente à nova solicitação de retirada |
|  | O Sistema compila os dados essenciais da notificação (identificador da OS, nome do mecânico e quantidade de itens) |
|  | O Sistema cria uma nova notificação somente para o perfil estoquista com o estado "Não Lida” |

### Fluxo Alternativo

Não identificado.

|  |  |
| --- | --- |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 3, o Sistema não encontra nenhum utilizador ativo mapeado com a função ("role") de estoquista. |
|  | O Sistema regista a notificação no grupo de "Gerente de Operações" e “Atendentes” como contingência. |

| **Pós Condição** | O estoquista é informado da demanda pendente e pode iniciar imediatamente o processo físico de *picking* e baixa de inventário |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF36
--------------------------------------------------
Titulo: O Sistema deve monitorar OS de produto retirado de estoque
Descrição: Processo de governação que vincula a baixa física de um produto no almoxarifado à Ordem de Serviço correspondente, rastreando o seu ciclo de vida no pátio até ao faturamento ou devolução, prevenindo perdas ou cobranças indevidas de material não aplicado.

| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Gerente de Operações, Estoquista |
| **Pré Condições** | A OS possui produtos vinculados em seu escopo, uma Retirada de Estoque foi realizada e confirmada no almoxarifado para esta OS. |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema intercepta o evento de confirmação de Retirada de Estoque |
|  | O Sistema associa o identificador da movimentação de estoque ao histórico cronológico da OS correspondente |
|  | O Sistema atualiza o total consolidado de peças retiradas para aquela OS |
|  | Durante a transição da OS para o status "Finalizada" (RF33 ), o Sistema realiza o batimento de dados entre a quantidade de produtos vinculada na OS e a quantidade física retirada no estoque |
|  | O Sistema permite o encerramento da OS se os totais coincidirem |

### Fluxo Alternativo

Não identificado.

|  |  |
| --- | --- |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 4, o Sistema detecta que a quantidade de um produto vinculada na OS difere da quantidade total que sofreu baixa física no estoque |
|  | O Sistema bloqueia a transação de mudança de status da OS para "Finalizada” |
|  | O Sistema emite um alerta na tela para o usuário, listando os produtos divergentes e exigindo a regularização da retirada ou a devolução física do excedente para liberar o encerramento |

| **Pós Condição** | A integridade financeira e física da OS é mantida, impedindo que veículos sejam liberados com peças não faturadas ou com desvios no inventário |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF37
--------------------------------------------------
Titulo: O Sistema deve atualizar reserva, estoque e OS ao final de cada atendimento
Descrição: Processo transacional automatizado que ocorre imediatamente após a sinalização de finalização do atendimento de uma Ordem de Serviço (OS). O sistema efetua a baixa definitiva das reservas lógicas, consolida os saldos físicos no estoque e altera o status da OS, garantindo a integridade dos dados entre o pátio e o almoxarifado.

| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Mecânico |
| **Pré Condições** | A Ordem de Serviço deve estar no status "Em Execução”, o Mecânico deve ter acionado o comando de finalização do atendimento (RF33 ), a validação de consistência entre itens vinculados e produtos fisicamente retirados (RF36 ) deve ter retornado sucesso. |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema intercepta o comando de finalização de atendimento da OS |
|  | O Sistema localiza todos os registros de Reserva (RF20  / RF25 ) associados àquela OS |
|  | O Sistema remove as reservas lógicas encontradas (liberando o saldo para que o cálculo de *Estoque Disponível* desconsidere o bloqueio temporário) |
|  | O Sistema converte o status da movimentação de estoque física (Kardex) relacionada àquela retirada de "Reservado/Em Trânsito Interno" para "Baixa por Consumo em OS" de forma definitiva |
|  | O Sistema altera o status da Ordem de Serviço para "OS Finalizada” |
|  | O Sistema persiste todas as alterações de maneira atômica no banco de dados |

### Fluxo Alternativo

Não identificado.

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 4 ou 5, o Sistema detecta que um registro de produto envolvido sofreu alteração simultânea por outro processo ou que a conexão com a base de dados falhou |
|  | O Sistema interrompe toda a operação imediatamente |
|  | O Sistema aplica um Rollback completo na transação (a OS permanece "Em Execução", as reservas permanecem ativas e nenhuma quantidade física é baixada) |
|  | O Sistema registra o erro de persistência interna e notifica o usuário para tentar a operação novamente |

| **Pós Condição** | As reservas são eliminadas por consumo, a quantidade de produtos em estoque é oficialmente reduzida no balanço físico e a OS transita de forma consolidada para o status "OS Finalizada", pronta para as etapas de faturamento. |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF38
--------------------------------------------------
Titulo: O Sistema deve gerar uma fatura para OS finalizada
Descrição: Processo de consolidação financeira que traduz o esforço técnico e os materiais aplicados numa Ordem de Serviço concluída para um documento de cobrança comercial (Fatura), viabilizando o pagamento pelo cliente.

| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Atendente ou Gerente de Operações |
| **Pré Condições** | A Ordem de Serviço deve ter o status alterado para "Finalizada" (RF33 ), todos os serviços e produtos vinculados à OS devem possuir valores de venda válidos registrados. |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema intercepta a consolidação do encerramento técnico da OS |
|  | O Sistema compila os valores totais de serviços executados e peças aplicadas |
|  | O Sistema aplica eventuais descontos negociados no orçamento de origem |
|  | O Sistema instancia um novo documento do tipo "Fatura" vinculado à OS e ao Cliente |
|  | O Sistema atribui à Fatura o status "Aguardando Pagamento” |
|  | O Sistema persiste a Fatura no banco de dados |
|  | O Sistema notifica a interface de Atendimento de que o faturamento do veículo está liberado |

### Fluxo Alternativo

Não identificado.

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  |  |
|  |  |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 2, o Sistema detecta que um produto ou serviço consumido possui o valor de venda zerado ou nulo, não caracterizado formalmente como cortesia |
|  | O Sistema aborta a geração da fatura |
|  | O Sistema emite um alerta informando a necessidade de precificação e revisão dos itens pendentes antes da emissão financeira |

| **Pós Condição** | A oficina obtém um título financeiro rastreável que autoriza o recebimento de valores do cliente e a posterior liberação do veículo. |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF39
--------------------------------------------------
Titulo: O Sistema deve informar o pagamento de uma fatura
Descrição: Processo financeiro que permite dar baixa e registar a quitação, total ou parcial, de uma Fatura vinculada a uma Ordem de Serviço (OS), atualizando o fluxo comercial e permitindo a posterior libertação do veículo ao cliente.

| **Ator Principal** | Atendente ou Gerente de Operações. |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | A Fatura deve estar previamente emitida com o status "Aguardando Pagamento" ou "Pago Parcialmente". |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
| O Ator Principal acede aos detalhes da Fatura através do identificador da OS ou do Cliente |  |
| O Ator Principal aciona a opção "Registar Pagamento" |  |
| O Ator Principal insere o valor recebido e a forma de pagamento (Dinheiro, Cartão, Transferência/PIX) |  |
|  | O Sistema valida se o valor informado é coerente com o saldo devedor da Fatura |
|  | O Sistema persiste o registo do pagamento na base de dados |
|  | O Sistema atualiza o saldo devedor e altera o status da Fatura para "Paga” |
|  | O Sistema emite um evento de domínio notificando a quitação financeira |
|  | O Sistema exibe um aviso de sucesso e disponibiliza a emissão do recibo na tela |

### Fluxo Alternativo

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 4, o Sistema identifica que o valor informado é inferior ao saldo devedor total |
|  | O Sistema regista a transação, abate o montante do saldo e altera o status da Fatura para "Pago Parcialmente" |
|  | O ciclo interrompe-se aqui até à inserção de novos pagamentos |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 4, o Sistema detecta que o montante inserido supera o saldo devedor atual da Fatura |
|  | O Sistema bloqueia a operação de salvaguarda |
|  | O Sistema apresenta a mensagem de erro "Valor informado excede o saldo devedor da fatura" e impede a persistência |

| **Pós Condição** | A Fatura é atualizada financeiramente, viabilizando a alteração automática ou manual do ciclo da OS para "OS Entregue". |
| --- | --- |

==================================================

## REQUISITO FUNCIONAL: RF40
--------------------------------------------------
Titulo: O Sistema atualizar e encerrar a OS após o pagamento da fatura
Descrição: Processo sistêmico de integração entre domínios que reage à quitação total de uma Fatura e consolida o encerramento do ciclo de vida da Ordem de Serviço, alterando seu estado para viabilizar a entrega física do veículo.

| **Ator Principal** | Sistema |
| --- | --- |
| **Atores Secundários** | Sistema |
| **Pré Condições** | A Fatura vinculada à Ordem de Serviço deve atingir o estado "Paga" (RF38 ), a Ordem de Serviço correspondente deve encontrar-se num estado pré-faturamento válido ("OS Finalizada"). |

### **Fluxo Principal**

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | O Sistema interceta o evento de domínio emitido pelo módulo financeiro confirmando a liquidação da Fatura |
|  | O Sistema extrai o identificador da OS contido na carga do evento |
|  | O Sistema localiza o registro da Ordem de Serviço na base de dados |
|  | O Sistema valida a transição de estado da OS |
|  | O Sistema altera o estado da OS de "OS Finalizada" para "OS Entregue” |
|  | O Sistema persiste a alteração e registra a transição na trilha de auditoria |

### Fluxo Alternativo

Não identificado.

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  |  |
|  |  |

### Fluxo de Exceção

| **Ações do Ator** | **Ações do Sistema** |
| --- | --- |
|  | No passo 4, o Sistema detecta que a OS não se encontra no estado "OS Finalizada" (ex: encontra-se suspensa ou já foi entregue) |
|  | O Sistema aborta a transição automática da OS |
|  | O Sistema registra uma anomalia de integração no log interno para intervenção gerencial |

| **Pós Condição** | A Ordem de Serviço atinge o fim da sua esteira operacional e comercial, sinalizando que a oficina não possui mais pendências técnicas ou financeiras com aquele veículo. |
| --- | --- |

==================================================

