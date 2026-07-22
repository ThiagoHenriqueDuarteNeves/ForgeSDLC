"""Testes determinísticos da ingestão (chunking) — sem LLM, sem banco."""

from src.ingest import chunk_text, parse_material


def test_chunk_texto_curto_vira_um_chunk():
    chunks = chunk_text("uma frase curta", page=3)
    assert len(chunks) == 1
    assert chunks[0].text == "uma frase curta"
    assert chunks[0].page == 3


def test_chunk_janela_com_sobreposicao():
    # 1000 palavras, janela 400, overlap 100 => passo 300 => 3 janelas
    words = [f"w{i}" for i in range(1000)]
    chunks = chunk_text(" ".join(words), page=None, chunk_words=400, overlap_words=100)
    assert len(chunks) == 3
    # primeira janela: w0..w399; segunda começa em w300 (sobreposição de 100)
    assert chunks[0].text.split()[0] == "w0"
    assert chunks[1].text.split()[0] == "w300"
    # a sobreposição existe: fim da 1ª e início da 2ª compartilham palavras
    assert chunks[0].text.split()[-1] == "w399"
    assert "w300" in chunks[0].text.split()


def test_chunk_deterministico():
    txt = " ".join(f"p{i}" for i in range(500))
    assert chunk_text(txt) == chunk_text(txt)


def test_parse_txt_e_paste():
    blocks = parse_material(b"linha um\nlinha dois", "txt")
    assert len(blocks) == 1
    assert "linha um" in blocks[0].text
    assert blocks[0].page is None
