## Tabela: Usuarios
### Descrição: Armazena os dados socioeconômicos e o desempenho acadêmico dos discente do curso de Sistemas de Informação da UFPA(Universidade Federal do Pará) Campus-Cametá


| Coluna                 | Tipo         | Nulo?   | Descrição                                                                        | Padrão                       |
|:-----------------------|:-------------|:--------|:---------------------------------------------------------------------------------|:-----------------------------|
| id                     | INTEGER      | False   | Identificador único do banco de dados                                            | 10                           |
| nome                   | VARCHAR(100) | True    | Nome completo do aluno                                                           | Felipe Souza Ferreira        |
| data_de_nascimento     | VARCHAR      | True    | Data de nascimento do discente                                                   | 31/02/1987                   |
| matricula              | INTEGER      | False   | O número único de matricula do discente                                          | 090913282541                 |
| primeiro_ano_eletivo   | VARCHAR(10)  | True    | Ano em que o discente começou a cursar                                           | 2031                         |
| CRG                    | FLOAT        | False   | Nota média acadêmica do discente                                                 | 6.767                        |
| periodo                | VARCHAR(15)  | False   | Periodo em que foi realizada a pesquisa                                          | 2027.(1 e 2)                 |
| genero                 | VARCHAR(20)  | True    | Autodeclaração de genero do discente                                             | Feminino                     |
| polo                   | VARCHAR(15)  | True    | Polo em que o discente está vinculado                                            | Oeiras                       |
| cor_etnia              | VARCHAR(10)  | True    | Autodeclaração de cor/etnia do discente                                          | Pardo                        |
| pcd                    | VARCHAR(5)   | True    | Declaração do discente sobre a deficiência                                       | Sim/Não                      |
| tipo_deficiencia       | VARCHAR(100) | True    | Declaração do tipo de deficiência do discente                                    | Física                       |
| renda                  | VARCHAR(150) | True    | Declaração da renda mensal família do discente                                   | Até 1 salário mínimo         |
| deslocamento           | VARCHAR(150) | True    | Declaração do tipo de transporte principal do discente                           | Bicicleta/A pé               |
| trabalho               | VARCHAR(150) | True    | Declaração do discente se trabalha e de qual o tipo de vínculo empregatício      | Sim, informal                |
| assistencia_estudantil | VARCHAR(5)   | True    | Declaração do discente se recebe assistência estudantil                          | Sim/ Não                     |
| saude_mental           | VARCHAR(10)  | True    | Declaração da saúde mental do discente                                           | Boa                          |
| estresse               | VARCHAR(50)  | True    | Declaração do nivel de estresse do discente                                      | Sim, ocasionalmente          |
| acompanhamento         | VARCHAR(20)  | True    | Declaração do discente sobre acompanhamento psicologico                          | Nunca                        |
| escolaridade_pai       | VARCHAR(20)  | True    | Declaração do discente sobre o grau de escolaridade do proprio pai               | Ensino Médio completo        |
| escolaridade_mae       | VARCHAR(20)  | True    | Declaração do discente sobre o grau de escolaridade do proprio mãe               | Pós-graduação                |
| qtd_computador         | INTEGER      | True    | Declaração do discente sobre a quantidade de computadores na casa                | 2                            |
| qtd_celular            | INTEGER      | True    | Declaração do discente sobre a quantidade celulares na casa                      | 2                            |
| computador_proprio     | VARCHAR(5)   | True    | Declaração da posse do computador proprio do discente                            | Sim/ Não                     |
| gasto_internet         | VARCHAR(30)  | True    | Declaração do gasto com internet do discente                                     | Entre R\$ 50,00 a R\$ 150,00 |
| acesso_internet        | VARCHAR(5)   | True    | Declaração do acesso a internet na casa do proprio discente                      | As vezes                     |
| tipo_moradia           | VARCHAR(10)  | True    | Declaração da situação da moradia do discente                                    | Cedida                       |
| data_hora              | VARCHAR(20)  | True    | Data e hora em que foi coletado e finalizado a pesquisa feita pelo discente      | 2025-10-29 18:28:37          |
