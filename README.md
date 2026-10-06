# Dashboard Dahruj

Aplicação independente para acompanhamento de vendas por unidade e consultor.
Contém Dashboard, Relatório Por Gerente e Relatório Por Consultor, com os
indicadores, faturamento, filtros, gráficos e exportações Excel. Usa a identidade
visual Dahruj: mesma logo, tema, cores, cartões e disposição das telas.

Verbas não são consultadas, calculadas, exibidas nem exportadas. O aplicativo não
inclui páginas de verbas, estoque, lançamentos ou histórico, nem funções de
gravação. A consulta usa uma lista explícita de colunas de `vw_base_tidy`.

## Executar

Na pasta deste projeto:

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Configure `.streamlit/secrets.toml` conforme `.streamlit/secrets.example.toml`.
A seção `[mysql]` deve apontar para o mesmo serviço e banco Aiven usados pelo
dashboard principal online. A seção local `[mysql_online]`, quando existente,
corresponde à seção `[mysql]` deste aplicativo. Não use o banco local por engano.
As conexões usam TLS com validação do certificado; se a Aiven exigir uma CA
própria, forneça `ssl_ca_pem` nos Secrets ou `ssl_ca` com o caminho do certificado.

## Publicar em outro link no Streamlit

1. Use o conteúdo desta pasta como raiz de um repositório separado, incluindo
   `.streamlit/config.toml`, `assets/logo.png` e `requirements.txt`.
2. Crie um novo app no Streamlit Community Cloud, com `app.py` como arquivo principal.
3. Em Advanced settings → Secrets, copie a seção `[mysql]` do arquivo local
   `.streamlit/secrets.toml`, incluindo o certificado completo em `ssl_ca_pem`.
   Não envie `.streamlit/secrets.toml` ao GitHub; ele está no `.gitignore`.
4. Escolha o endereço do novo app e publique.

Se usar um repositório com vários projetos, selecione `Dash Dahruj Lite/app.py`
como entrada e mantenha o tema em `.streamlit/config.toml` **na raiz do
repositório**, pois o Streamlit executa a partir dessa raiz. O repositório separado
evita interferência nas configurações do aplicativo já publicado.

Referências: [publicação](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy),
[organização dos arquivos](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/file-organization)
e [Secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## Atualização dos dados

Os dois aplicativos leem a mesma `vw_base_tidy` no Aiven; não há cópia de base,
importador adicional ou sincronização entre aplicativos. Ao salvar ou importar
vendas **no banco online**, o novo aplicativo passa a ler os dados atualizados.
Alterações somente no banco local não atualizam o Aiven.

A leitura tem cache de 60 segundos. A sessão aberta verifica a atualização a
cada 60 segundos, limpa o cache de leitura e redesenha a página mantendo os
filtros válidos. Espere aproximadamente um minuto após a confirmação da gravação
no Aiven, acrescido do tempo de consulta. Abas suspensas pelo navegador podem
atualizar apenas quando voltarem a ficar ativas. Esse funcionamento usa
[fragments do Streamlit](https://docs.streamlit.io/develop/api-reference/execution-flow/st.fragment).

Alterações de layout ou código no outro aplicativo não são copiadas automaticamente.

## Usuário de banco dedicado

Recomenda-se um usuário exclusivo com `SELECT` apenas nas colunas usadas pelo app.
O arquivo `permissoes_leitura.sql` contém o comando para o administrador executar
após criar esse usuário no Aiven. Ele não cria nem modifica tabelas ou registros.
O aplicativo já usa transações de leitura; o privilégio restrito no banco também
impede que a credencial consulte as tabelas de verbas ou grave dados.

Não é necessário executar os scripts de esquema ou carga do projeto principal.

## Verificar

```powershell
python -m unittest discover -s tests -v
```

Os testes usam dados sintéticos para conferir navegação, indicadores, exportações
e exclusão de verbas, sem gravar no Aiven.
