#!/usr/bin/env python3
# ==========================================================
#  TASKFORGE — Gerenciador de Produtividade e Agenda (CLI)
# ==========================================================
#
#  Um gerenciador de tarefas em linha de comando, escrito em
#  Python, focado em organização pessoal, disciplina e
#  acompanhamento de tempo por tarefa.
#
#  Funcionalidades principais:
#  - Criação, edição e exclusão de tarefas
#  - Definição de prazos (data e hora)
#  - Cronômetro por tarefa (último tempo e tempo total)
#  - Remoção automática de tarefas vencidas
#  - Checagem periódica em thread daemon
#  - Persistência local automática em arquivo JSON
#
#  Persistência:
#  - Arquivo local: tarefas.json
#
#  Requisitos:
#  - Python 3.8+
#  - Apenas biblioteca padrão
#  - Execução como root
#
# ----------------------------------------------------------
#  Autor: Bandeirinha
#  Projeto: TASKFORGE
#  Versão: 1.0.0
#  Licença: GNU General Public License v3.0 (GPLv3)
# ----------------------------------------------------------
#
#  Este software é livre e distribuído SEM QUALQUER GARANTIA.
#  Consulte o arquivo LICENSE para mais informações.
#
# ==========================================================

import json
import os
import threading
import time
from datetime import datetime
from uuid import uuid4

DB_FILE = "tarefas.json"
DATE_FMT = "%Y-%m-%d %H:%M"

lock = threading.Lock()


# =========================
# Utilidades básicas
# =========================

def agora():
    return datetime.now()


def gerar_id():
    return str(uuid4())


def parse_prazo(s):
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), DATE_FMT)
    except ValueError:
        return None


def format_prazo(dt):
    if not dt:
        return "—"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
    return dt.strftime(DATE_FMT)


# =========================
# Persistência
# =========================

def carregar_tarefas():
    if not os.path.exists(DB_FILE):
        return []

    with open(DB_FILE, "r", encoding="utf-8") as f:
        try:
            tarefas = json.load(f)
        except Exception:
            return []

    # migração automática: remove campos obsoletos
    for t in tarefas:
        t.pop("tipo", None)

    return tarefas


def salvar_tarefas(tarefas):
    with lock:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(tarefas, f, indent=4, ensure_ascii=False)


# =========================
# Lógica de tarefas
# =========================

def remover_vencidas(notificar=True):
    tarefas = carregar_tarefas()
    agora_dt = agora()

    restantes = []
    removidas = []

    for t in tarefas:
        prazo = None
        if t.get("prazo"):
            try:
                prazo = datetime.fromisoformat(t["prazo"])
            except Exception:
                prazo = None

        if prazo and prazo <= agora_dt:
            removidas.append(t)
        else:
            restantes.append(t)

    if removidas:
        salvar_tarefas(restantes)
        if notificar:
            for r in removidas:
                print(f"[AUTO] Removida por prazo vencido: [{r['id'][:8]}] {r['titulo']}")


def criar_tarefa_interativa():
    titulo = input("Título: ").strip()
    if not titulo:
        print("Título é obrigatório.")
        return

    descricao = input("Descrição (opcional): ").strip()

    qtd_raw = input("Quantidade (opcional): ").strip()
    quantidade = int(qtd_raw) if qtd_raw.isdigit() else None

    prazo_raw = input(f"Prazo ({DATE_FMT}) ou Enter para nenhum: ").strip()
    prazo = parse_prazo(prazo_raw)
    if prazo_raw and not prazo:
        print("Formato de data inválido.")
        return

    tarefa = {
        "id": gerar_id(),
        "titulo": titulo,
        "descricao": descricao,
        "quantidade": quantidade,
        "prazo": prazo.isoformat() if prazo else None,
        "concluida": False,
        "criado_em": agora().isoformat(),
        "ultimo_tempo_seg": 0,
        "total_tempo_seg": 0,
    }

    tarefas = carregar_tarefas()
    tarefas.append(tarefa)
    salvar_tarefas(tarefas)

    print("Tarefa criada:", tarefa["id"][:8])


def listar_tarefas_interativo():
    remover_vencidas(notificar=True)

    tarefas = carregar_tarefas()
    if not tarefas:
        print("Nenhuma tarefa registrada.")
        return

    pendentes = [t for t in tarefas if not t.get("concluida")]
    concluidas = [t for t in tarefas if t.get("concluida")]

    def imprimir(lista, titulo):
        print(f"\n--- {titulo} ({len(lista)}) ---")
        for t in lista:
            qtd = t.get("quantidade") or "—"
            prazo = format_prazo(t.get("prazo"))
            print(f"[{t['id'][:8]}] {t['titulo']} | qtd:{qtd} | prazo:{prazo}")
            if t.get("descricao"):
                print("   desc:", t["descricao"])
            if t.get("ultimo_tempo_seg"):
                m, s = divmod(t["ultimo_tempo_seg"], 60)
                tm, ts = divmod(t.get("total_tempo_seg", 0), 60)
                print(f"   último: {m}m{s}s | total: {tm}m{ts}s")

    imprimir(pendentes, "Pendentes")
    imprimir(concluidas, "Concluídas")


def selecionar_tarefa(prompt="ID ou parte do título: "):
    tarefas = carregar_tarefas()
    q = input(prompt).strip().lower()
    if not q:
        return None

    encontrados = [
        t for t in tarefas
        if q in t["id"] or q in t["titulo"].lower()
    ]

    if not encontrados:
        print("Nenhuma tarefa encontrada.")
        return None

    if len(encontrados) == 1:
        return encontrados[0]

    for i, t in enumerate(encontrados, 1):
        print(i, f"[{t['id'][:8]}] {t['titulo']}")

    idx = input("Escolha: ").strip()
    return encontrados[int(idx) - 1] if idx.isdigit() and 0 < int(idx) <= len(encontrados) else None


def editar_tarefa_interativa():
    t = selecionar_tarefa()
    if not t:
        return

    print("Deixe em branco para manter.")
    titulo = input(f"Título [{t['titulo']}]: ").strip()
    if titulo:
        t["titulo"] = titulo

    descricao = input(f"Descrição [{t.get('descricao','')}]: ").strip()
    if descricao != "":
        t["descricao"] = descricao

    qtd = input(f"Quantidade [{t.get('quantidade','')}]: ").strip()
    if qtd == "":
        pass  # mantém valor atual
    elif qtd.isdigit():
        t["quantidade"] = int(qtd)
    else:
        t["quantidade"] = None

    prazo_raw = input(f"Prazo [{format_prazo(t.get('prazo'))}]: ").strip()
    if prazo_raw:
        prazo = parse_prazo(prazo_raw)
        if prazo:
            t["prazo"] = prazo.isoformat()

    if input("Marcar como concluída? (s/N): ").strip().lower() in ("s", "sim"):
        t["concluida"] = True # desmarcar se NÃO
    else:
        t["concluida"] = False

    tarefas = carregar_tarefas()
    for i, item in enumerate(tarefas):
        if item["id"] == t["id"]:
            tarefas[i] = t
            break

    salvar_tarefas(tarefas)
    print("Tarefa atualizada.")


def excluir_tarefa_interativa():
    t = selecionar_tarefa()
    if not t:
        return

    if input(f"Excluir [{t['titulo']}]? (s/N): ").strip().lower() in ("s", "sim"):
        tarefas = [x for x in carregar_tarefas() if x["id"] != t["id"]]
        salvar_tarefas(tarefas)
        print("Tarefa excluída.")


def marcar_tarefa():
    t = selecionar_tarefa()
    if not t:
        return

    tarefas = carregar_tarefas()
    for i, item in enumerate(tarefas):
        if item["id"] == t["id"]:
            tarefas[i]["concluida"] = not item.get("concluida", False)
            salvar_tarefas(tarefas)
            print("Estado alterado.")
            return


def iniciar_cronometro():
    t = selecionar_tarefa("Tarefa a cronometrar: ")
    if not t:
        return

    print("Enter inicia | Enter para parar | q cancela")
    if input().strip().lower() == "q":
        return

    inicio = time.time()
    input()
    dur = int(time.time() - inicio)

    tarefas = carregar_tarefas()
    for i, item in enumerate(tarefas):
        if item["id"] == t["id"]:
            item["ultimo_tempo_seg"] = dur
            item["total_tempo_seg"] = item.get("total_tempo_seg", 0) + dur
            tarefas[i] = item
            salvar_tarefas(tarefas)
            m, s = divmod(dur, 60)
            print(f"Cronômetro salvo: {m}m{s}s")
            return


# =========================
# Loop principal
# =========================

def checador_periodico():
    while True:
        remover_vencidas(notificar=True)
        time.sleep(60)


def menu_principal():
    print("\n\n\t=== TASKFORGE ===\n")
    threading.Thread(target=checador_periodico, daemon=True).start()

    while True:
        op = input("\n[A]Adicionar [L]Listar [C]Cronometrar [E]Editar [M]Concluir [D]Excluir [Q]Sair: ").strip().lower()
        if op == "q":
            break
        elif op == "a":
            criar_tarefa_interativa()
        elif op == "l":
            listar_tarefas_interativo()
        elif op == "c":
            iniciar_cronometro()
        elif op == "e":
            editar_tarefa_interativa()
        elif op == "m":
            marcar_tarefa()
        elif op == "d":
            excluir_tarefa_interativa()
        else:
            print("Opção inválida.")

if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        salvar_tarefas([])
    print("Gerenciador iniciado | Datas:", DATE_FMT)
    menu_principal()
