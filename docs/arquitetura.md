# Arquitetura

Cliente -> Nginx:8090 -> /static e /media nos volumes
                     -> demais rotas -> Django/Gunicorn:8000 -> PostgreSQL:5432
                                                               ^
                                                        DBeaver: localhost:15432

O Dockerfile constrói a imagem Django. O entrypoint aguarda o banco, executa migrations, coleta estáticos e inicia o Gunicorn. O Compose conecta serviços, rede e volumes.
