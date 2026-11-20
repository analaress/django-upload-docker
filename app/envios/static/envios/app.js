/* Comportamentos da Central de Arquivos:
 * - descreve os arquivos escolhidos, inclusive quando chegam por drag-and-drop;
 * - consulta o status das miniaturas e atualiza os cartões sem recarregar a
 *   página quando a Lambda termina.
 */
(function () {
    "use strict";

    function descreverArquivos(arquivos) {
        if (!arquivos || !arquivos.length) {
            return "Nenhuma imagem selecionada";
        }
        if (arquivos.length === 1) {
            return arquivos[0].name;
        }
        return (
            arquivos.length +
            " imagens: " +
            Array.from(arquivos)
                .map(function (arquivo) {
                    return arquivo.name;
                })
                .join(", ")
        );
    }

    function configurarZonaUpload(zona) {
        var input = zona.querySelector('input[type="file"]');
        var rotulo = zona.querySelector(".nome-arquivo");
        if (!input || !rotulo) {
            return;
        }

        function atualizarRotulo() {
            rotulo.textContent = descreverArquivos(input.files);
        }

        input.addEventListener("change", atualizarRotulo);
        atualizarRotulo();

        var profundidade = 0;

        function entrar(evento) {
            evento.preventDefault();
            evento.stopPropagation();
            profundidade += 1;
            zona.classList.add("arrastando");
        }

        function sobre(evento) {
            evento.preventDefault();
            evento.stopPropagation();
            zona.classList.add("arrastando");
        }

        function sair(evento) {
            evento.preventDefault();
            evento.stopPropagation();
            profundidade = Math.max(0, profundidade - 1);
            if (profundidade === 0) {
                zona.classList.remove("arrastando");
            }
        }

        function soltar(evento) {
            evento.preventDefault();
            evento.stopPropagation();
            profundidade = 0;
            zona.classList.remove("arrastando");

            var arquivos = evento.dataTransfer && evento.dataTransfer.files;
            if (!arquivos || !arquivos.length) {
                return;
            }

            try {
                var transferencia = new DataTransfer();
                Array.from(arquivos).forEach(function (arquivo) {
                    transferencia.items.add(arquivo);
                });
                input.files = transferencia.files;
            } catch (erro) {
                // Alguns navegadores aceitam o FileList do evento diretamente.
                try {
                    input.files = arquivos;
                } catch (erroAtribuicao) {
                    return;
                }
            }

            atualizarRotulo();
            input.dispatchEvent(new Event("change", { bubbles: true }));
        }

        zona.addEventListener("dragenter", entrar);
        zona.addEventListener("dragover", sobre);
        zona.addEventListener("dragleave", sair);
        zona.addEventListener("drop", soltar);
    }

    function criarLink(destino, texto) {
        var link = document.createElement("a");
        link.className = "link-arquivo";
        link.href = destino;
        link.textContent = texto;
        return link;
    }

    function mostrarProcessada(cartao, dados) {
        cartao.dataset.processada = "1";

        var miniatura = cartao.querySelector(".miniatura");
        if (miniatura) {
            var imagem = document.createElement("img");
            imagem.src = dados.url;
            imagem.alt = "Miniatura de " + (cartao.dataset.nome || "imagem");
            imagem.loading = "lazy";

            var etiqueta = document.createElement("span");
            etiqueta.className = "etiqueta etiqueta-ok";
            etiqueta.textContent = "Processada";

            miniatura.replaceChildren(imagem, etiqueta);
        }

        var acoes = cartao.querySelector(".acoes-imagem");
        if (acoes) {
            acoes.replaceChildren(
                criarLink(cartao.dataset.originalUrl, "Baixar original"),
                criarLink(dados.download_url, "Baixar miniatura")
            );
        }
    }

    function configurarAtualizacaoMiniaturas() {
        var pendentes = Array.from(
            document.querySelectorAll('[data-processada="0"][data-status-url]')
        );
        if (!pendentes.length) {
            return;
        }

        function consultar(cartao) {
            fetch(cartao.dataset.statusUrl, {
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            })
                .then(function (resposta) {
                    if (!resposta.ok) {
                        throw new Error("status " + resposta.status);
                    }
                    return resposta.json();
                })
                .then(function (dados) {
                    if (!dados.processada) {
                        return;
                    }
                    mostrarProcessada(cartao, dados);
                    if (cartao._intervaloStatus) {
                        clearInterval(cartao._intervaloStatus);
                        delete cartao._intervaloStatus;
                    }
                })
                .catch(function () {
                    // Mantém o cartão em processamento e tenta no próximo ciclo.
                });
        }

        pendentes.forEach(function (cartao) {
            consultar(cartao);
            cartao._intervaloStatus = setInterval(function () {
                consultar(cartao);
            }, 2500);
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        document.querySelectorAll(".botao-upload").forEach(configurarZonaUpload);
        configurarAtualizacaoMiniaturas();
    });
})();
