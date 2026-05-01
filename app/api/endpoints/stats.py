from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
import numpy as np
import scipy.stats as st
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import random
import base64
from typing import Callable, List, Dict, Tuple
from scipy.stats import chi2

from app.core.fastapi_config import templates as jinja_templates

router = APIRouter(prefix="/stats", tags=["stats"])
_global_rng = np.random.default_rng(random.randint(1, 1_000_052))


def fig_to_base64() -> str:
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("ascii")
    plt.close()
    return f"data:image/png;base64,{b64}"


def plot_histogram_img(
    data: np.ndarray,
    title: str,
    vline: float | None = None,
    bins: int = 20,
    density: bool = False,
    color: str = "blue",
) -> str:
    plt.figure(figsize=(18, 10), dpi=300)
    plt.hist(data, bins=bins, alpha=0.85, color=color, edgecolor="black", density=density)
    if vline is not None:
        plt.axvline(vline, color="red", linestyle="dashed", linewidth=3.0, label=f"theta = {vline:.3f}")

    plt.title(title, fontsize=18, fontweight='bold')
    plt.xlabel('Значения', fontsize=14)
    plt.ylabel('Частота', fontsize=14)
    if vline is not None:
        plt.legend(fontsize=12)

    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    return fig_to_base64()


def get_sampler_and_info(distribution: str, rng: np.random.Generator) -> Tuple[Callable[[float, int], np.ndarray], float, str]:
    name = distribution.lower() if isinstance(distribution, str) else "normal"

    if name in ("cauchy", "c"):
        def sampler(loc: float, size: int) -> np.ndarray:
            return rng.standard_cauchy(size=size) + loc

        return sampler, (np.pi / 2), "Cauchy"

    def sampler(loc: float, size: int) -> np.ndarray:
        return rng.normal(loc=loc, scale=1.0, size=size)

    return sampler, (np.sqrt(np.pi / 2)), "Normal(\u03B8,1)"


def run_experiment_for_theta(
    sampler: Callable[[float, int], np.ndarray],
    theta: float,
    n: int,
    repeats: int,
) -> Dict[str, np.ndarray]:
    medians = np.empty(repeats, dtype=float)
    means = np.empty(repeats, dtype=float)

    for i in range(repeats):
        sample = sampler(theta, n)
        medians[i] = float(np.median(sample))
        means[i] = float(np.mean(sample))

    return {"medians": medians, "means": means}


def build_result_images(
    medians: np.ndarray,
    means: np.ndarray,
    theta: float,
    n: int,
    asymp_median_std: float,
    dist_name: str,
    bins: int = 20,
) -> Dict[str, str]:
    imgs: Dict[str, str] = {
        "medians": plot_histogram_img(medians, title=f"Гистограмма выборочных медиан ({dist_name})", vline=theta, color="tab:blue", bins=bins),
        "means": plot_histogram_img(means, title=f"Гистограмма выборочных средних ({dist_name})", vline=theta, color="tab:green", bins=bins)
    }

    val_med = np.sqrt(n) * (medians - theta)
    plt.figure(figsize=(18, 10), dpi=150)
    plt.hist(val_med, bins=bins, alpha=0.75, color="tab:purple", density=True, edgecolor="black")
    x = np.linspace(val_med.min(), val_med.max(), 300)
    pdf = st.norm.pdf(x, loc=0, scale=asymp_median_std)
    plt.plot(x, pdf, "r-", lw=3.0, label=f"N(0, {asymp_median_std:.3f})")
    plt.title(f"sqrt(n)*(median - theta) ({dist_name})", fontsize=18, fontweight='bold')
    plt.xlabel('Значение', fontsize=14)
    plt.ylabel('Частота', fontsize=14)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.25)
    plt.tight_layout()
    imgs["median_norm"] = fig_to_base64()

    val_mean = np.sqrt(n) * (means - theta)
    imgs["mean_norm"] = plot_histogram_img(val_mean, title=f"sqrt(n)*(mean - theta) ({dist_name})", bins=bins, density=True, color="tab:orange")

    return imgs


@router.get("/", response_class=HTMLResponse)
async def stats_gallery(request: Request):
    return jinja_templates.TemplateResponse("stats_gallery.html", {"request": request})


@router.get("/t6", response_class=HTMLResponse)
async def stats_ui(request: Request):
    return jinja_templates.TemplateResponse("stats_ui.html", {"request": request})


@router.post("/t6/run", name="stats_run")
async def stats_run(
    distribution: str = Form("cauchy"),
    runs: int = Form(1),
    n: int = Form(1000),
    repeats: int = Form(101),
    bins: int = Form(20),
    seed: str | None = Form(None),
):
    runs = max(1, int(runs))
    n = max(1, int(n))
    repeats = max(1, int(repeats))
    bins_val = int(bins)
    bins_val = max(5, min(200, bins_val))

    seed_val: int | None = None
    if seed is not None:
        s = str(seed).strip()
        if s != "":
            try:
                seed_val = int(s)
            except Exception:
                return JSONResponse({"error": "seed must be an integer or empty"}, status_code=400)

    theta_rng = np.random.default_rng(int(seed_val)) if seed_val is not None else _global_rng
    thetas = theta_rng.uniform(-10, 10, size=runs)

    sampler, asymp_median_std, dist_name = get_sampler_and_info(distribution, np.random.default_rng(random.randint(1, 1_000_000)))

    results: List[Dict] = []
    for theta in thetas:
        res = run_experiment_for_theta(sampler, float(theta), n=n, repeats=repeats)
        imgs = build_result_images(res["medians"], res["means"], float(theta), n, asymp_median_std, dist_name, bins=bins_val)
        results.append({"theta": float(theta), "images": imgs})

    return JSONResponse({"results": results})


@router.get("/t10", response_class=HTMLResponse)
async def t10_ui(request: Request):
    return jinja_templates.TemplateResponse("t10_ui.html", {"request": request})


@router.post("/t10/run", name="t10_run")
async def t10_run_endpoint(
    n: int = Form(1000),
    simulations: int = Form(1000),
    seed: str | None = Form(None)
):
    n = max(10, min(10000, n))
    simulations = max(10, min(5000, simulations))

    seed_val = None
    if seed is not None:
        s = str(seed).strip()
        if s != "":
            try:
                seed_val = int(s)
            except Exception:
                return JSONResponse({"error": "Сид должен быть целым числом (или пустым для сида по умолчанию)"}, status_code=400)

    rng = np.random.default_rng(seed_val)

    sample = rng.normal(0, 1, n)
    dn_vals = []

    for k in range(1, n + 1):
        sub = np.sort(sample[:k])
        fx = st.norm.cdf(sub)
        i_arr = np.arange(1, k + 1)
        dp = np.abs(i_arr / k - fx)
        dm = np.abs((i_arr - 1) / k - fx)
        dn_vals.append(max(np.max(dp), np.max(dm)))

    plt.figure(figsize=(18, 10), dpi=150)
    plt.plot(range(1, n + 1), dn_vals, lw=2, color='tab:blue')
    plt.title("Зависимость D_n от n", fontsize=18, fontweight='bold')
    plt.xlabel("n", fontsize=14)
    plt.ylabel("D_n", fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    img_d_n = fig_to_base64()

    samples = rng.normal(0, 1, (simulations, n))

    i_arr = np.arange(1, n + 1)
    S = np.sort(samples, axis=1)
    fx = st.norm.cdf(S)
    dp = np.abs((i_arr / n) - fx)
    dm = np.abs(((i_arr - 1) / n) - fx)
    dn_per_sim = np.maximum(np.max(dp, axis=1), np.max(dm, axis=1))
    sqrt_n_dn = np.sqrt(n) * dn_per_sim

    plt.figure(figsize=(18, 10), dpi=300)
    x_vals = np.linspace(-1, 10, 500)

    sqrt_n_dn_arr = np.asarray(sqrt_n_dn)
    ecdf_vals = np.mean(sqrt_n_dn_arr[:, None] <= x_vals[None, :], axis=0)

    plt.plot(x_vals, ecdf_vals, label="Эмпирическая функция распределения sqrt(n)*D_n", lw=4, color='tab:orange', alpha=0.9)
    plt.plot(x_vals, st.kstwobign.cdf(x_vals), label="Функция распределения Колмогорова K(x)", lw=2, ls="--", color='black')

    plt.title("Сравнение эмпирической функции распределения sqrt(n)*D_n и теоретической K(x)", fontsize=18, fontweight='bold')
    plt.xlabel("$x$", fontsize=14)
    plt.ylabel("Вероятность / Распределение", fontsize=14)
    plt.legend(fontsize=14)
    plt.xlim(-1, 10)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    img_cdf = fig_to_base64()

    return JSONResponse({
        "d_n_plot": img_d_n,
        "cdf_plot": img_cdf
    })


@router.get("/t11_12", response_class=HTMLResponse)
async def t11_12_ui(request: Request):
    return jinja_templates.TemplateResponse("t11_12_ui.html", {"request": request})


@router.post("/t11_12/run", name="t11_12_run")
async def t11_12_run(
    distribution: str = Form("normal"),
    samples: str = Form("5, 10, 100"),
    seed: str | None = Form(None)
):
    try:
        n_vals = [int(x.strip()) for x in samples.split(",") if x.strip()]
    except Exception:
        n_vals = [5, 10, 100]

    seed_val = None
    if seed and seed.strip():
        try: seed_val = int(seed.strip())
        except: pass
    rng = np.random.default_rng(seed_val)

    images = []

    if distribution == "normal":
        theta_vals = np.linspace(-10, 10, 201)
        z = st.norm.ppf(0.975)
    else:
        theta_vals = np.linspace(0.1, 10, 100)
        z = st.norm.ppf(0.975)

    for n in n_vals:
        means = []
        lows = []
        highs = []

        count = 0

        for th in theta_vals:
            if distribution == "normal":
                data = rng.normal(th, 1.0, n)
                m = np.mean(data)
                hw = z / np.sqrt(n)
                lows.append(m - hw)
                highs.append(m + hw)

                if th < lows[-1] or th > highs[-1]:
                    count += 1

                means.append(m)
            else:
                data = rng.poisson(th, n)
                # m = (4 * np.mean(data) + (n * 0.05) ** (-1)) ** 0.5
                # hw = (n * 0.05) ** (-0.5) if m > 0 else 0

                '''
                alpha = 0.05
                S = np.sum(data)
                low = chi2.ppf(alpha/2, 2*S) / (2*n) if S > 0 else 0
                high = chi2.ppf(1-alpha/2, 2*(S+1)) / (2*n)
                lows.append(low)
                highs.append(high)
                means.append(S/n)
                '''

                m = np.mean(data) + z ** 2 / (2 * n)
                hw = z * np.sqrt(np.mean(data) / n + (z ** 2) / (4 * n ** 2))
                lows.append(m - hw)
                highs.append(m + hw)
                means.append(m)

        plt.figure(figsize=(14, 8), dpi=150)
        plt.plot(theta_vals, theta_vals, label="Истинное значение theta", color="black", lw=2, linestyle="--")
        score = (len(theta_vals) - count) / len(theta_vals) * 100
        plt.text(0.05, 0.7, f"Покрытие: {score:.1f}%", transform=plt.gca().transAxes, fontsize=12, verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

        yerr = [
            np.array(means) - np.array(lows),
            np.array(highs) - np.array(means)
        ]
        plt.errorbar(theta_vals, means, yerr=yerr, fmt="none", color="tab:blue", alpha=0.5, label="95% Доверительный интервал")
        plt.scatter(theta_vals, means, s=10, color="tab:red", label="Выборочное среднее (оценка theta)", zorder=3)

        plt.title(f"Доверительные интервалы для {distribution.capitalize()} (n = {n})", fontsize=16)
        plt.xlabel("Истинное theta", fontsize=14)
        plt.ylabel("Оцененное theta", fontsize=14)
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()
        images.append({"title": f"n = {n}", "src": fig_to_base64()})

    return JSONResponse({"images": images})


@router.get("/t8", response_class=HTMLResponse)
async def t8_ui(request: Request):
    return jinja_templates.TemplateResponse("t8_ui.html", {"request": request})


@router.post("/t8/run", name="t8_run")
async def t8_run(
    theta: float = Form(5.0),
    n: int = Form(100),
    simulations: int = Form(10000)
):
    rng = np.random.default_rng()
    sims = rng.uniform(0, theta, (simulations, n))

    theta1 = (n + 1) / n * np.max(sims, axis=1)
    # theta1 = np.max(sims, axis=1)
    theta2 = 2 * np.mean(sims, axis=1)

    var_opt_emp = np.var(theta1)
    var_mom_emp = np.var(theta2)

    var_opt_theo = theta**2 / (n**2 + 2 * n)
    var_mom_theo = (theta**2) / (3 * n)

    plt.figure(figsize=(14, 8), dpi=300)
    plt.hist(theta1, bins=50, alpha=0.7, color="tab:blue", label="theta_1 = (n+1)/n * max(X) (Оптимальная)")
    plt.hist(theta2, bins=50, alpha=0.7, color="tab:orange", label="theta_2 = 2*mean(X) (Моментов)")
    plt.axvline(theta, color="red", lw=2, linestyle="--", label="Истинное θ")
    plt.title(f"Распределение оценок для U[0, {theta}] (n={n})", fontsize=16)
    plt.xlabel("Значение оценки", fontsize=14)
    plt.ylabel("Частота", fontsize=14)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    img_hist = fig_to_base64()

    n_space = np.arange(10, min(1000, n*5 + 1), 10)
    # var_th_1 = (n_space * theta**2) / (((n_space + 1)**2) * (n_space + 2))
    var_th_1 = theta**2 / ((n_space**2) + (n_space * 2))
    var_th_2 = (theta**2) / (3 * n_space)

    plt.figure(figsize=(14, 8), dpi=300)
    plt.plot(n_space, var_th_1, color="tab:blue", lw=3, label="Var(theta_1) ~ O(n^-2)")
    plt.plot(n_space, var_th_2, color="tab:orange", lw=3, label="Var(theta_2) ~ O(n^-1)")
    plt.yscale("log")
    plt.title("Сравнение дисперсий оценок (Асимптотика)", fontsize=16)
    plt.xlabel("Размер выборки (n)", fontsize=14)
    plt.ylabel("Теоретическая дисперсия (log scale)", fontsize=14)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    img_var = fig_to_base64()

    emp_var_1 = []
    emp_var_2 = []
    emp_mean_1 = []
    emp_mean_2 = []

    for m in n_space:
        sims_m = rng.uniform(0, theta, (simulations, m))
        t1_m = (m + 1) / m * np.max(sims_m, axis=1)
        t2_m = 2 * np.mean(sims_m, axis=1)
        emp_var_1.append(np.var(t1_m, ddof=0))
        emp_var_2.append(np.var(t2_m, ddof=0))
        emp_mean_1.append(np.mean(t1_m))
        emp_mean_2.append(np.mean(t2_m))

    emp_var_1 = np.array(emp_var_1)
    emp_var_2 = np.array(emp_var_2)
    emp_mean_1 = np.array(emp_mean_1)
    emp_mean_2 = np.array(emp_mean_2)

    plt.figure(figsize=(14, 8), dpi=300)
    plt.plot(n_space, emp_var_1, label='Эмпирическая Var(theta_1)', color='tab:blue', lw=2)
    plt.plot(n_space, emp_var_2, label='Эмпирическая Var(theta_2)', color='tab:orange', lw=2)
    plt.plot(n_space, var_th_1, '--', color='tab:blue', lw=1.5, alpha=0.7, label='Теоретическая Var(theta_1)')
    plt.plot(n_space, var_th_2, '--', color='tab:orange', lw=1.5, alpha=0.7, label='Теоретическая Var(theta_2)')
    plt.yscale('log')
    plt.title('Эмпирическая дисперсия оценок vs Теоретическая (log scale)', fontsize=16)
    plt.xlabel('Размер выборки (n)', fontsize=14)
    plt.ylabel('Дисперсия (log scale)', fontsize=14)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    img_emp_var = fig_to_base64()

    sel_idx = [0, len(n_space) // 2, len(n_space) - 1]
    sel_n = [int(n_space[i]) for i in sel_idx]

    saved_biases_t1 = {}
    saved_biases_t2 = {}

    for m in sel_n:
        sims_m = rng.uniform(0, theta, (simulations, m))
        t1_m = (m + 1) / m * np.max(sims_m, axis=1)
        t2_m = 2 * np.mean(sims_m, axis=1)
        saved_biases_t1[m] = t1_m - theta
        saved_biases_t2[m] = t2_m - theta

    cols = len(sel_n)
    plt.figure(figsize=(6 * cols, 10), dpi=300)
    for j, m in enumerate(sel_n):
        plt.subplot(2, cols, 1 + j)
        data = saved_biases_t1[m]
        plt.hist(data, bins=50, alpha=0.85, color='tab:blue', edgecolor='black')
        plt.title(f'Theta1 (n={m})', fontsize=14)
        plt.xlabel('Theta_hat - theta', fontsize=12)
        plt.ylabel('Частота', fontsize=12)
        plt.grid(True, alpha=0.25)

        plt.subplot(2, cols, cols + 1 + j)
        data2 = saved_biases_t2[m]
        plt.hist(data2, bins=50, alpha=0.85, color='tab:orange', edgecolor='black')
        plt.title(f'Theta2 (n={m})', fontsize=14)
        plt.xlabel('Theta_hat - theta', fontsize=12)
        plt.ylabel('Частота', fontsize=12)
        plt.grid(True, alpha=0.25)

    plt.suptitle('Распределение смещений оценок для нескольких n (theta_hat - theta)', fontsize=16, fontweight='bold')
    plt.tight_layout(rect=(0, 0.03, 1, 0.95))
    img_bias = fig_to_base64()

    maxs = np.max(sims, axis=1)
    val_t1 = n * (theta - maxs)
    val_t2 = np.sqrt(n) * (theta2 - theta)

    plt.figure(figsize=(14, 8), dpi=300)
    plt.hist(val_t1, bins=50, density=True, alpha=0.75, color='tab:blue', edgecolor='black')
    x1 = np.linspace(0, max(val_t1.max(), 1e-6), 300)
    exp_pdf = (1.0 / theta) * np.exp(-x1 / theta)
    plt.plot(x1, exp_pdf, 'r--', lw=2, label=f'Exp(scale={theta:.3f}) (теор.)')
    plt.title('n*(theta - X_(n)) для максимума (сходимость к экспоненциальному)', fontsize=16)
    plt.xlabel('Значение', fontsize=14)
    plt.ylabel('Плотность', fontsize=14)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    img_t1_norm = fig_to_base64()

    plt.figure(figsize=(14, 8), dpi=300)
    plt.hist(val_t2, bins=50, density=True, alpha=0.75, color='tab:orange', edgecolor='black')
    plt.title('sqrt(n)*(theta2 - theta) (проверка асимптотической нормальности)', fontsize=16)
    plt.xlabel('Значение', fontsize=14)
    plt.ylabel('Плотность', fontsize=14)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    img_t2_norm = fig_to_base64()

    return JSONResponse({
        "theta": theta,
        "n": n,
        "simulations": simulations,
        "var_opt_emp": float(var_opt_emp),
        "var_opt_theo": float(var_opt_theo),
        "var_mom_emp": float(var_mom_emp),
        "var_mom_theo": float(var_mom_theo),
        "images": [
            {"title": "Гистограмма распределения оценок", "src": img_hist},
            {"title": "Асимптотика дисперсий", "src": img_var},
            {"title": "Эмпирическая дисперсия оценок", "src": img_emp_var},
            {"title": "Смещение оценок vs n", "src": img_bias},
            {"title": "n*(theta - X_(n)) (максимум)", "src": img_t1_norm},
            {"title": "sqrt(n)*(theta2 - theta)", "src": img_t2_norm}
        ]
    })


@router.get("/t13", response_class=HTMLResponse)
async def t13_ui(request: Request):
    return jinja_templates.TemplateResponse("t13_ui.html", {"request": request})


@router.post("/t13/run", name="t13_run")
async def t13_run(
    n: int = Form(1000),
    p_values: str = Form("0.95,0.9,0.8"),
    bootstrap_iters: int = Form(1000),
    seed: str | None = Form(None),
):
    n = max(1, int(n))
    bootstrap_iters = max(50, min(10000, int(bootstrap_iters)))

    try:
        p_list = [float(x.strip()) for x in p_values.split(",") if x.strip()]
        p_list = [p for p in p_list if 0.0 < p < 1.0]
        if not p_list:
            p_list = [0.95, 0.9, 0.8]
    except Exception:
        p_list = [0.95, 0.9, 0.8]

    seed_val = None
    if seed is not None:
        s = str(seed).strip()
        if s != "":
            try:
                seed_val = int(s)
            except Exception:
                return JSONResponse({"error": "seed must be an integer or empty"}, status_code=400)

    rng = np.random.default_rng(seed_val)

    mu = 70.0
    sigma = 10.0

    results: List[Dict] = []

    sample = rng.normal(loc=mu, scale=sigma, size=n)

    for p in p_list:
        theo_q = float(st.norm.ppf(p, loc=mu, scale=sigma))
        sample_q = float(np.quantile(sample, p))

        B = bootstrap_iters
        bs_idx = rng.integers(0, n, size=(B, n))
        bs_samples = sample[bs_idx]
        bs_q = np.quantile(bs_samples, p, axis=1)

        bs_std = float(np.std(bs_q, ddof=1))
        ci_low, ci_high = np.percentile(bs_q, [5, 95])

        plt.figure(figsize=(16, 8), dpi=300)
        plt.hist(bs_q, bins=50, alpha=0.85, color='tab:blue', edgecolor='black')
        plt.axvline(sample_q, color='red', lw=3.0, linestyle='--', label=f"sample q (p={p}) = {sample_q:.3f}")
        plt.axvline(theo_q, color='green', lw=3.0, linestyle='--', label=f"theoretical q = {theo_q:.3f}")
        plt.title(f"Bootstrap-распределение оценки квантиля p={p} (n={n}, B={B})", fontsize=16, fontweight='bold')
        plt.xlabel('Оценки квантиля', fontsize=14)
        plt.ylabel('Частота', fontsize=14)
        plt.legend(fontsize=12)
        plt.grid(True, alpha=0.25)
        plt.tight_layout()
        img_hist = fig_to_base64()

        plt.figure(figsize=(10, 4), dpi=300)
        lower = sample_q - ci_low
        upper = ci_high - sample_q
        yerr = np.array([[lower], [upper]])
        plt.errorbar([0], [sample_q], yerr=yerr, fmt='o', color='tab:orange', capsize=8, lw=2)
        plt.axhline(theo_q, color='green', lw=2, ls='--', label='Теоретический квантиль')
        plt.xlim(-1, 1)
        plt.title(f"Оценка квантиля p={p}", fontsize=14)
        plt.xticks([])
        plt.ylabel('Квантиль', fontsize=12)
        plt.legend()
        plt.grid(True, alpha=0.2)
        plt.tight_layout()
        img_ci = fig_to_base64()

        results.append({
            "p": p,
            "theoretical": round(theo_q, 4),
            "sample_quantile": round(sample_q, 4),
            "bootstrap_std": round(bs_std, 6),
            "ci_95": [round(float(ci_low), 4), round(float(ci_high), 4)],
            "images": {
                "hist": img_hist,
                "ci": img_ci
            }
        })

    return JSONResponse({"sample_n": n, "bootstrap_iters": B, "seed": seed_val, "results": results})
