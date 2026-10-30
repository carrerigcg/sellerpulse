# Política de Privacidade do SellerPulse

**Versão:** 2026-11-v1

**Última atualização:** 30 de outubro de 2026

## 1. Quem somos

O SellerPulse é um serviço de análise de vendas para vendedores do Mercado
Livre, operado por **Guilherme Carreri Giampietro** ("SellerPulse", "nós").

Encarregado pelo tratamento de dados pessoais (LGPD, art. 41), ou canal de
atendimento ao titular: **Guilherme Carreri Giampietro**, pelo e-mail
**carreri.gcg@gmail.com**.

## 2. Os dois papéis que temos

O SellerPulse trata dois tipos de dado pessoal, e o nosso papel é diferente em
cada um:

- **Os seus dados, como usuário e cliente do SellerPulse** (e-mail, senha, uso
  do serviço, aceite e assinatura). Aqui somos o **controlador**: decidimos como
  esses dados são tratados.
- **Os dados dos seus compradores**, que chegam junto com os seus pedidos do
  Mercado Livre. Aqui somos o **operador**: tratamos esses dados **em seu
  nome** e só para gerar as análises que você pediu. Você, como vendedor, é o
  controlador desses dados em relação aos seus clientes.

## 3. Quais dados tratamos

### 3.1 Dados da sua conta no SellerPulse
- E-mail e senha. A senha é guardada pelo provedor de autenticação em forma
  irreversível (hash); nós não temos acesso a ela.
- Datas de cadastro e de acesso.

### 3.2 Dados da contratação e da assinatura
- **Prova do aceite dos Termos:** versão aceita, data e hora, endereço IP e
  navegador usado.
- **Assinatura:** plano, ciclo (mensal ou anual), datas de início, de validade
  e de cancelamento.
- **Dados técnicos da cobrança, enviados pelo Asaas:** os códigos que o Asaas
  usa para identificar o cliente, a cobrança e a assinatura, valores, situação,
  datas, forma de pagamento e links da fatura e do comprovante.

**Não guardamos** o seu nome de cobrança, CPF ou CNPJ, endereço de cobrança,
telefone nem dados do cartão. Você os informa diretamente na página do Asaas. Se
um aviso do Asaas trouxer CPF ou CNPJ, telefone ou dados de cartão, esses campos
são descartados antes de gravar.

### 3.3 Dados que vêm da sua conta do Mercado Livre
Quando você autoriza a conexão pelo fluxo oficial do Mercado Livre,
recebemos:

- **Credencial de acesso (token).** Fica guardada **cifrada**. A senha da sua
  conta do Mercado Livre nunca passa pelo SellerPulse.
- **Seus pedidos dos últimos seis meses, e os seguintes:** data, situação,
  valores, comissão do Mercado Livre, cupons, itens vendidos, quantidades e
  preços, e o registro do pedido como o Mercado Livre o entrega, sem os campos
  descartados indicados na seção 3.4.
- **Seus anúncios:** título, categoria e as visitas que cada anúncio recebeu.
- **Seus envios:** o custo do frete que coube a você.

### 3.4 Dados dos seus compradores (como operador)
Dentro dos pedidos, o Mercado Livre entrega e nós guardamos:
- o **identificador** e o **apelido** do comprador no Mercado Livre;
- **os valores do pagamento** que vêm no registro do pedido: valor pago,
  valor devolvido, forma de pagamento, número de parcelas, situação e datas.

**Não guardamos** nome, e-mail, telefone, endereço ou CPF do comprador, nem
número de cartão. Os identificadores de cartão, de pagador e de autorização
que o Mercado Livre envia junto com o pedido são **descartados antes de
gravar**, porque nenhuma análise precisa deles.

### 3.5 Dados que você informa
- O **custo de cada produto**, com a data a partir da qual ele vale.
- O que você nos escrever ao pedir suporte, por e-mail ou WhatsApp.

### 3.6 Dados técnicos
- **Cookies de sessão**, para manter você conectado. São essenciais: sem eles
  o login não funciona.
- Um registro no armazenamento do seu navegador (`localStorage`) que lembra
  se você já viu o tutorial de cada tela.
- Registros técnicos dos servidores (por exemplo, erros e horário das
  requisições), usados para manter o serviço funcionando.

**Não usamos** cookies de publicidade, rastreamento de terceiros nem
ferramentas de análise de comportamento.

## 4. Para que usamos e com que base legal

| finalidade | dados | base legal (LGPD, art. 7º) |
| --- | --- | --- |
| Criar e manter a sua conta | e-mail, senha | execução de contrato (V) |
| Contratar, cobrar e controlar o acesso ao plano | assinatura, dados técnicos da cobrança | execução de contrato (V) |
| Provar o aceite dos Termos | versão, data, IP, navegador | exercício regular de direitos (VI) |
| Importar e atualizar seus dados do Mercado Livre | token, pedidos, anúncios, envios | execução de contrato (V) |
| Calcular as análises (margem, curva ABC, clientes, desempenho dos anúncios) | pedidos, custos informados, dados dos compradores | execução de contrato (V), em nome do vendedor-controlador |
| Atender você | mensagens de suporte | execução de contrato (V) |
| Segurança e prevenção de fraude e abuso | registros técnicos | legítimo interesse (IX) |
| Cumprir obrigações legais | o que a lei exigir | obrigação legal (II) |

**Não vendemos nem alugamos dados. Não usamos os seus dados nem os dos seus
compradores para publicidade.**

## 5. Com quem compartilhamos

Usamos fornecedores para operar o serviço:

| fornecedor | para quê | onde |
| --- | --- | --- |
| Supabase | banco de dados e autenticação | Estados Unidos (Ohio) |
| Render | servidor da aplicação | Estados Unidos (Oregon) |
| Vercel | hospedagem do site | Estados Unidos e rede global |
| Asaas | cobrança: recebe diretamente de você os dados de pagamento | empresa brasileira; conforme a política do Asaas |
| Mercado Livre | origem dos dados; a conexão é autorizada por você | conforme a política do Mercado Livre |
| Google (Gmail) e WhatsApp | suporte, quando você nos procura por esses canais | conforme a política de cada um |



O **Asaas** trata os dados de pagamento conforme a política dele, e por isso a
recomendamos também.

Também podemos compartilhar dados quando a lei ou uma ordem de autoridade
competente exigir.

## 6. Transferência internacional

Supabase, Render e Vercel armazenam ou processam os dados nos **Estados Unidos**.
A transferência acontece para executar o contrato com você (LGPD, art. 33,
inciso IX), com fornecedores que adotam salvaguardas de segurança compatíveis
com a LGPD.

## 7. Por quanto tempo guardamos

- **Enquanto a sua conta existir**, guardamos os dados para manter as
  análises.
- **Ao cancelar a assinatura ou deixar o plano vencer**, os dados continuam, e
  voltam a aparecer se você contratar de novo, por até **12 meses** sem plano
  ativo. A credencial do Mercado Livre é apagada 30 dias depois do fim do plano.
- **Ao desconectar o Mercado Livre**, apagamos imediatamente a credencial de
  acesso e paramos de buscar dados novos. Os dados já importados continuam,
  para você não perder o histórico, até você pedir a exclusão.
- **Ao pedir a exclusão da conta**, apagamos a conta e os dados ligados a ela em
  até **30 dias**. Cópias de segurança dos fornecedores, se existirem, expiram no prazo de cada um.
- **Mantemos pelo prazo legal** o que a lei obrigar ou o que for preciso para
  defender direitos, como a prova do aceite e os registros da cobrança, por
  5 anos, e os registros de acesso à aplicação, por 6 meses (Marco Civil da
  Internet, art. 15).

## 8. Seus direitos

Pela LGPD (art. 18), você pode pedir:
- confirmação de que tratamos seus dados, e acesso a eles;
- correção de dados incompletos, inexatos ou desatualizados;
- anonimização, bloqueio ou eliminação de dados desnecessários ou tratados
  em desconformidade;
- portabilidade. Nos planos com a aba Exportar, boa parte dos seus dados já pode
  ser baixada em CSV;
- eliminação dos dados e informação sobre com quem compartilhamos.

Para exercer esses direitos, escreva para **carreri.gcg@gmail.com**.
Respondemos em até **15 dias**.

**Pedidos de compradores:** se um comprador seu nos procurar, vamos
encaminhar o pedido a você, que é o controlador desses dados, e apoiar o
atendimento.

## 9. Segurança

- A comunicação é cifrada (HTTPS).
- A credencial do Mercado Livre fica cifrada em repouso.
- Cada vendedor só acessa os próprios dados. Todas as consultas filtram pelo
  vendedor da sessão, e regras de segurança no próprio banco de dados (RLS)
  bloqueiam o acesso direto aos dados de outro vendedor.
- Os avisos de pagamento só são aceitos com um token secreto do Asaas.
- O acesso administrativo é restrito.

Nenhum sistema é infalível. Em caso de incidente de segurança que possa
causar risco ou dano relevante, comunicaremos você e a ANPD, nos termos da
lei.

## 10. Menores de idade

O SellerPulse é destinado a vendedores maiores de 18 anos ou a empresas, e
não coleta dados de menores de forma intencional.

## 11. Mudanças nesta política

Se esta política mudar de forma relevante, avisamos pelo e-mail da conta ou
dentro do serviço antes de a mudança valer.

## 12. Contato

**carreri.gcg@gmail.com** · WhatsApp: **(11) 99234-4633** 
