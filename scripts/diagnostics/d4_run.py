"""COMANDO 204, D4: as exclusoes que atingem as usinas existentes. Somente leitura; grava so em D4_dados/.

Le validation_units (F7b), as camadas alinhadas da F2a (contagens de WorldCover 2020 v100, contagens de declividade, GHS-SMOD) e o WDPA bruto.
Nada roda de fase; nenhum arquivo de outputs/ e escrito.
"""
from __future__ import annotations

import json
import math

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import yaml
from rasterio.windows import Window

import d1_common as c

OUT = c.OUT / "D4_dados"
OUT.mkdir(parents=True, exist_ok=True)
CLASSES = [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100]
CLASS_NAME = {10: "arvores", 20: "arbustos", 30: "pastagem", 40: "lavoura", 50: "construido", 60: "solo_exposto", 70: "neve_gelo", 80: "agua", 90: "areas_umidas", 95: "mangue", 100: "musgo"}
LA = yaml.safe_load(open(c.REPO / "config" / "experiments.yaml", encoding="utf-8"))["land_availability"]["technologies"]
SAMPLES = 14400.0
SETTLEMENT_MIN = 13  # GHS-SMOD: classe 13 (aglomerado rural, vila) ou mais
IUCN_ORDER = ["Ia", "Ib", "II", "III", "IV", "V", "VI", "Not Reported", "Not Applicable", "Not Assigned"]


def slope_above(counts: np.ndarray, pct: float) -> np.ndarray:
    """Parcela das amostras de declividade acima de `pct` por cento (tangente), com a parcela do compartimento do limiar tomada em proporcao (M-F2b-01, E4)."""
    t = math.degrees(math.atan(pct / 100.0))
    j = int(math.floor(t))
    frac = t - j
    tot = counts.sum(axis=1).astype("float64")
    above = counts[:, j + 1 :].sum(axis=1) + (1.0 - frac) * counts[:, j]
    with np.errstate(divide="ignore", invalid="ignore"):
        return above / tot


def mean_slope_deg(counts: np.ndarray) -> np.ndarray:
    mid = np.arange(counts.shape[1]) + 0.5
    tot = counts.sum(axis=1).astype("float64")
    with np.errstate(divide="ignore", invalid="ignore"):
        return (counts * mid).sum(axis=1) / tot


def sample_all(path, lon, lat) -> np.ndarray:
    with rasterio.open(path) as s:
        return np.array(list(s.sample(list(zip(lon, lat))))).astype("float64")


def background(path, mask_path, fn) -> dict:
    """Media sobre os pixels validos do pais, em faixas de linhas, de fn(bloco 2D (n, bandas)) -> dict de arrays 1D por pixel."""
    sums: dict = {}
    n = 0
    with rasterio.open(path) as s, rasterio.open(mask_path) as m:
        step = 256
        for r0 in range(0, s.height, step):
            h = min(step, s.height - r0)
            w = Window(0, r0, s.width, h)
            mk = (m.read(1, window=w) != m.nodata).reshape(-1)
            if not mk.any():
                continue
            blk = s.read(window=w).reshape(s.count, -1).T[mk].astype("float64")
            nod = s.nodata
            if nod is not None:
                blk = blk[(blk != nod).all(axis=1)]
            if len(blk) == 0:
                continue
            for k, v in fn(blk).items():
                sums[k] = sums.get(k, 0.0) + float(np.nansum(v))
            n += len(blk)
    return {k: v / n for k, v in sums.items()} | {"n_pixels": n}


def distance_to_settlement_m(lon, lat, sett_path, min_class=SETTLEMENT_MIN):
    """Distancia (m) do ponto ao pixel de assentamento mais proximo (borda do pixel), numa janela de 7 x 7 pixels; 0 se o proprio pixel e assentamento; NaN se nao ha nenhum na janela."""
    with rasterio.open(sett_path) as s:
        a = s.read(1)
        tr = s.transform
        nod = s.nodata
    sett = (a >= min_class) & (a <= 30) & (a != nod)
    px = abs(tr.a)
    out = np.full(len(lon), np.nan)
    for i, (x, y) in enumerate(zip(lon, lat)):
        col = int(math.floor((x - tr.c) / tr.a))
        row = int(math.floor((y - tr.f) / tr.e))
        best = None
        for dr in range(-3, 4):
            for dc in range(-3, 4):
                r, cc = row + dr, col + dc
                if 0 <= r < a.shape[0] and 0 <= cc < a.shape[1] and sett[r, cc]:
                    x0, y1 = tr.c + cc * tr.a, tr.f + r * tr.e  # canto superior esquerdo
                    x1, y0 = x0 + tr.a, y1 + tr.e
                    dx = max(x0 - x, 0.0, x - x1) * 111320.0 * math.cos(math.radians(y))
                    dy = max(min(y0, y1) - y, 0.0, y - max(y0, y1)) * 110574.0
                    d = math.hypot(dx, dy)
                    best = d if best is None or d < best else best
        out[i] = np.nan if best is None else best
    return out, px


def wavg(v, w):
    v, w = np.asarray(v, dtype="float64"), np.asarray(w, dtype="float64")
    m = np.isfinite(v) & np.isfinite(w) & (w > 0)
    return float((v[m] * w[m]).sum() / w[m].sum()) if m.any() else float("nan")


res: dict = {}
rows_e5, rows_e5v, rows_e4, rows_e6, rows_e1, rows_unit = [], [], [], [], [], []
for iso in ("PRT", "IND", "BRA"):
    G = c.DATA / "outputs" / iso / "grid_alignment" / "artifacts"
    units = pd.read_parquet(c.DATA / "outputs" / iso / "external_validation" / "artifacts" / "validation_units.parquet")
    units = units[units["in_grid"] & units["valid_pixel"]].reset_index(drop=True)
    lon, lat = units["lon"].to_numpy(), units["lat"].to_numpy()
    lc = sample_all(G / f"{iso}_land_cover_counts_aligned.tif", lon, lat)
    sl = sample_all(G / f"{iso}_slope_counts_aligned.tif", lon, lat)
    slf = sample_all(G / f"{iso}_slope_counts_fabdem_aligned.tif", lon, lat)
    st = sample_all(G / f"{iso}_settlements_aligned.tif", lon, lat)[:, 0]
    dist, px = distance_to_settlement_m(lon, lat, G / f"{iso}_settlements_aligned.tif")
    wd = gpd.read_file(c.DATA / "raw" / "wdpa" / iso / f"{iso}_protected_areas_wdpa.geojson")[["IUCN_CAT", "wdpa_id", "name", "geometry"]]
    pts = gpd.GeoDataFrame(units[["gem_unit_id"]].copy(), geometry=gpd.points_from_xy(lon, lat), crs="EPSG:4326")
    j = gpd.sjoin(pts, wd.to_crs("EPSG:4326"), how="left", predicate="within")
    j["rank"] = j["IUCN_CAT"].map({k: i for i, k in enumerate(IUCN_ORDER)}).fillna(len(IUCN_ORDER))
    j = j.sort_values(["gem_unit_id", "rank"]).drop_duplicates("gem_unit_id")
    units = units.merge(j[["gem_unit_id", "IUCN_CAT", "wdpa_id"]], on="gem_unit_id", how="left")
    units["in_wdpa"] = units["wdpa_id"].notna()
    # ---- classes de cobertura
    shares = lc / SAMPLES
    for k, cl in enumerate(CLASSES):
        units[f"lc_{CLASS_NAME[cl]}"] = shares[:, k]
    units["lc_sem_classe"] = 1.0 - lc.sum(axis=1) / SAMPLES
    units["dist_assentamento_m"] = dist
    units["classe_ghs"] = st
    units["declividade_media_deg"] = mean_slope_deg(sl)
    units["declividade_media_deg_fabdem"] = mean_slope_deg(slf)
    units["dif_arquivos_declividade"] = np.abs(sl - slf).sum(axis=1)
    bg_lc = background(G / f"{iso}_land_cover_counts_aligned.tif", G / f"{iso}_grid_aligned.tif", lambda b: {f"lc_{CLASS_NAME[cl]}": b[:, k] / SAMPLES for k, cl in enumerate(CLASSES)})
    res[iso] = {"bg_lc": bg_lc, "n_units": int(len(units)), "px_deg": px}
    for tech in ("solar", "wind"):
        u = units[units["technology"] == tech].copy()
        if u.empty:
            continue
        la = LA[tech]
        excl = la["excluded_classes"]["levels"][la["excluded_classes"]["nominal"]]
        # E5 recalculado
        idx = np.flatnonzero(units["technology"].to_numpy() == tech)
        allowed = [k for k, cl in enumerate(CLASSES) if cl not in excl]
        e5 = 1.0 - lc[idx][:, allowed].sum(axis=1) / SAMPLES
        e5_err = float(np.abs(e5 - u["excluded_E5"].to_numpy()).max())
        # E4 recalculado para os tres cenarios, nos dois arquivos de declividade
        thr = {s: float(la["slope_max_pct"][s]) for s in ("restrictive", "central", "permissive")}
        e4 = {s: slope_above(sl[idx], v) for s, v in thr.items()}
        e4f = {s: slope_above(slf[idx], v) for s, v in thr.items()}
        err_main = float(np.nanmax(np.abs(e4["central"] - u["excluded_E4"].to_numpy())))
        err_fab = float(np.nanmax(np.abs(e4f["central"] - u["excluded_E4"].to_numpy())))
        u["E5_calc"] = e5
        for s in thr:
            u[f"E4_{s}"], u[f"E4f_{s}"] = e4[s], e4f[s]
        w = u["capacity_mw"].to_numpy()
        res[f"{iso} {tech}"] = {"n_units": int(len(u)), "capacity_mw": float(w.sum()), "E5_erro_max": e5_err, "E4_erro_max_arquivo_F3": err_main, "E4_erro_max_fabdem": err_fab, "limiares_declividade_pct": thr, "classes_excluidas": excl,
                                "n_exact": int((u["location_accuracy"] == "exact").sum()), "mw_exact": float(w[(u["location_accuracy"] == "exact").to_numpy()].sum()), "n_sem_ano": int(u["start_year"].isna().sum())}
        # vintage: WorldCover 2020
        u["vintage"] = np.where(u["start_year"].isna(), "sem ano", np.where(u["start_year"] <= 2019, "ate 2019", np.where(u["start_year"] == 2020, "2020", "2021 ou depois")))
        for acc_name, sub in (("todas", u), ("exact", u[u["location_accuracy"] == "exact"])):
            if sub.empty:
                continue
            ww = sub["capacity_mw"].to_numpy()
            row = {"par": f"{iso} {tech}", "localizacao": acc_name, "n": int(len(sub)), "mw": float(ww.sum()), "E5_medio": wavg(sub["excluded_E5"], ww), "frac_E5_ge_0_5": float(ww[sub["excluded_E5"].to_numpy() >= 0.5].sum() / ww.sum())}
            for cl in CLASSES:
                row[f"lc_{CLASS_NAME[cl]}"] = wavg(sub[f"lc_{CLASS_NAME[cl]}"], ww)
            row["lc_sem_classe"] = wavg(sub["lc_sem_classe"], ww)
            row["classes_excluidas"] = ",".join(str(x) for x in excl)
            rows_e5.append(row)
            for vint, sv in sub.groupby("vintage"):
                wv = sv["capacity_mw"].to_numpy()
                rows_e5v.append({"par": f"{iso} {tech}", "localizacao": acc_name, "vintage": vint, "n": int(len(sv)), "mw": float(wv.sum()), "construido": wavg(sv["lc_construido"], wv), "construido_fundo": bg_lc["lc_construido"], "solo_exposto": wavg(sv["lc_solo_exposto"], wv), "solo_exposto_fundo": bg_lc["lc_solo_exposto"],
                                 "lavoura": wavg(sv["lc_lavoura"], wv), "lavoura_fundo": bg_lc["lc_lavoura"], "arvores": wavg(sv["lc_arvores"], wv), "arvores_fundo": bg_lc["lc_arvores"], "E5_medio": wavg(sv["excluded_E5"], wv),
                                 "frac_construido_ge_0_5": float(wv[sv["lc_construido"].to_numpy() >= 0.5].sum() / wv.sum()), "frac_construido_ge_0_1": float(wv[sv["lc_construido"].to_numpy() >= 0.1].sum() / wv.sum())})
            # E4
            row4 = {"par": f"{iso} {tech}", "localizacao": acc_name, "n": int(len(sub)), "mw": float(ww.sum()), "declividade_media_deg_pond": wavg(sub["declividade_media_deg"], ww), "declividade_media_deg_fabdem_pond": wavg(sub["declividade_media_deg_fabdem"], ww),
                    "mediana_declividade_media_deg": float(np.median(sub["declividade_media_deg"])), "p90_declividade_media_deg": float(np.quantile(sub["declividade_media_deg"], 0.9)), "E4_registrado_medio": wavg(sub["excluded_E4"], ww)}
            for s in thr:
                row4[f"E4_{s}_medio"] = wavg(sub[f"E4_{s}"], ww)
                row4[f"frac_cap_E4_{s}_ge_0_5"] = float(ww[sub[f"E4_{s}"].to_numpy() >= 0.5].sum() / ww.sum())
                row4[f"frac_cap_E4_{s}_gt_0"] = float(ww[sub[f"E4_{s}"].to_numpy() > 0].sum() / ww.sum())
                row4[f"E4f_{s}_medio"] = wavg(sub[f"E4f_{s}"], ww)
            rows_e4.append(row4)
            # E6
            d = sub["dist_assentamento_m"].to_numpy()
            row6 = {"par": f"{iso} {tech}", "localizacao": acc_name, "n": int(len(sub)), "mw": float(ww.sum()), "E6_registrado_medio": wavg(sub["excluded_E6"], ww), "frac_cap_E6_ge_0_5": float(ww[sub["excluded_E6"].to_numpy() >= 0.5].sum() / ww.sum()), "frac_cap_E6_igual_1": float(ww[sub["excluded_E6"].to_numpy() >= 0.999].sum() / ww.sum()),
                    "frac_cap_proprio_pixel_assentamento": float(ww[(sub["classe_ghs"].to_numpy() >= SETTLEMENT_MIN) & (sub["classe_ghs"].to_numpy() <= 30)].sum() / ww.sum()), "frac_unid_proprio_pixel_assentamento": float(((sub["classe_ghs"] >= SETTLEMENT_MIN) & (sub["classe_ghs"] <= 30)).mean())}
            sb = {"restrictive": 1000.0, "central": 800.0 if tech == "wind" else 500.0, "permissive": 500.0 if tech == "wind" else 0.0}
            for s, m in sb.items():
                row6[f"frac_cap_ponto_dentro_{s}_{int(m)}m"] = float(ww[np.isfinite(d) & (d <= m) & (d >= 0)].sum() / ww.sum()) if m > 0 else float(ww[np.isfinite(d) & (d == 0)].sum() / ww.sum())
            row6["mediana_dist_m"] = float(np.nanmedian(d)) if np.isfinite(d).any() else float("nan")
            row6["frac_cap_sem_assentamento_na_janela"] = float(ww[~np.isfinite(d)].sum() / ww.sum())
            rows_e6.append(row6)
            # E1
            row1 = {"par": f"{iso} {tech}", "localizacao": acc_name, "n": int(len(sub)), "mw": float(ww.sum()), "E1_pixel_registrado_medio": wavg(sub["excluded_E1"], ww), "frac_cap_E1_pixel_ge_0_5": float(ww[sub["excluded_E1"].to_numpy() >= 0.5].sum() / ww.sum()),
                    "frac_cap_ponto_no_WDPA": float(ww[sub["in_wdpa"].to_numpy()].sum() / ww.sum()), "n_ponto_no_WDPA": int(sub["in_wdpa"].sum()),
                    "frac_cap_pixel_E1_gt_0_e_ponto_fora": float(ww[(sub["excluded_E1"].to_numpy() > 0) & (~sub["in_wdpa"].to_numpy())].sum() / ww.sum())}
            inside = sub[sub["in_wdpa"]]
            for cat, g in inside.groupby(inside["IUCN_CAT"].fillna("sem categoria")):
                row1[f"mw_{cat}"] = float(g["capacity_mw"].sum())
            rows_e1.append(row1)
        rows_unit.append(u[["technology", "gem_unit_id", "capacity_mw", "start_year", "location_accuracy", "excluded_E1", "excluded_E4", "excluded_E5", "excluded_E6", "in_wdpa", "IUCN_CAT", "lc_construido", "lc_solo_exposto", "lc_lavoura", "lc_arvores", "dist_assentamento_m", "classe_ghs", "declividade_media_deg"]].assign(pais=iso))
    print(iso, "ok", flush=True)

pd.DataFrame(rows_e5).to_csv(OUT / "D4_E5_composicao.csv", index=False)
pd.DataFrame(rows_e5v).to_csv(OUT / "D4_E5_vintage.csv", index=False)
pd.DataFrame(rows_e4).to_csv(OUT / "D4_E4.csv", index=False)
pd.DataFrame(rows_e6).to_csv(OUT / "D4_E6.csv", index=False)
pd.DataFrame(rows_e1).to_csv(OUT / "D4_E1.csv", index=False)
pd.concat(rows_unit).to_csv(OUT / "D4_unidades.csv", index=False)
json.dump(res, open(OUT / "D4_verificacoes.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("ok")
