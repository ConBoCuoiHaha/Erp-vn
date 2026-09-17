MODULES = []   # (code, name, odoo, phase, features)
ENTITIES = {}  # name -> dict
RELS = []      # (module, a, card, b, label)


def M(code, name, odoo, phase, features):
    MODULES.append(dict(code=code, name=name, odoo=odoo, phase=phase, features=features))


def E(mod, name, vn, odoo, desc, fields):
    rows = []
    for line in fields.strip().splitlines():
        p = [x.strip() for x in line.split('|')]
        while len(p) < 4:
            p.append('')
        rows.append(dict(f=p[0], t=p[1], k=p[2], m=p[3]))
    assert name not in ENTITIES, name
    ENTITIES[name] = dict(mod=mod, name=name, vn=vn, odoo=odoo, desc=desc, fields=rows)


def R(mod, a, card, b, label):
    RELS.append(dict(mod=mod, a=a, card=card, b=b, label=label))
