import csv
from pathlib import Path

TASK_MAP = {
    "RF01": "T02",
    "RF02": "T03",
    "RF03": "T05",
    "RF04": "T04",
    "RF05": "T02",
    "RF06": "T06",
    "RF07": "T08",
    "RF08": "T06",
    "RF09": "T04",
    "RF10": "T06",
    "RF11": "T06",
    "RF12": "T06",
    "RF13": "T06",
    "RF14": "T06",
    "RF15": "T07",
    "RF16": "T07",
    "RF17": "T07",
    "RF18": "T07",
    "RF19": "T08",
    "RF20": "T09",
    "RF21": "T09",
    "RF22": "T09",
    "RF23": "T09",
    "RF24": "T09",
    "RF25": "T09",
    "RF26": "T08",
    "RF27": "T08",
    "RF28": "T08",
    "RF29": "T05",
    "RF30": "T05, T10",
    "RF31": "T10",
    "RF32": "T10",
    "RF33": "T10",
    "RF34": "T10",
    "RF35": "T10",
    "RF36": "T10",
    "RF37": "T10",
    "RF38": "T11",
    "RF39": "T11",
    "RF40": "T11",
}

TASK_NAMES = {
    "T01": "Bootstrap do projeto e infraestrutura",
    "T02": "Gestão de clientes, identificação e autenticação administrativa",
    "T03": "Gestão de veículos",
    "T04": "Catálogo de serviços e composição serviço-produto",
    "T05": "Produtos, fornecedores e gestão de estoque",
    "T06": "Criação e composição de orçamento",
    "T07": "PDF do orçamento, envio por e-mail e aprovação do cliente",
    "T08": "Gestão e atribuição de ordens de serviço (OS)",
    "T09": "Reservas, solicitações de compra e recebimento de mercadorias",
    "T10": "Fila de execução, execução do serviço e retirada de estoque",
    "T11": "Faturamento e encerramento por pagamento",
    "T12": "Testes automatizados, validação de segurança e hardening da API",
}


def task_description(codes: str) -> str:
    if not codes:
        return ""
    parts = [
        f"{code.strip()} — {TASK_NAMES.get(code.strip(), code.strip())}"
        for code in codes.split(",")
    ]
    return " | ".join(parts)


def update_csv(path: Path) -> None:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
        fieldnames = [
            k for k in rows[0].keys() if k not in ("Tarefa", "Descricao da tarefa", "Descrição da tarefa")
        ]
    fieldnames.extend(["Tarefa", "Descrição da tarefa"])

    for row in rows:
        rf = (row.get("Identificador") or "").strip()
        codes = TASK_MAP.get(rf, "")
        row["Tarefa"] = codes
        row["Descrição da tarefa"] = task_description(codes)

    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated {path.name}: RF01 -> {rows[0]['Tarefa']}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    base = root / "requirements-export" / "part1" / "Particular e Compartilhado"
    files = [
        base
        / "Wiki"
        / "Banco de Dados"
        / "Requisitos"
        / "Requisitos 37e3d0beeb9f80769bdce514b67cdb34_all.csv",
        base / "Sem título 37e3d0beeb9f803caa6af79c87c560ed.csv",
    ]
    docs_out = root / "docs" / "requisitos-com-tarefas.csv"

    for path in files:
        update_csv(path)

    docs_out.write_text(files[0].read_text(encoding="utf-8-sig"), encoding="utf-8-sig")
    print(f"Copied to {docs_out}")


if __name__ == "__main__":
    main()
