# Utilidad para guardar las detecciones como imagenes PNG reales, con la figura y
# su etiqueta reconocida (estilo del enunciado: la caja con "Detecto: X").
#
# Esto es solo para la evidencia visual (screenshots del informe/slides). El nodo
# Raft y el protocolo NO dependen de esto; es una ayuda del Servidor de Testeo.
# Usa matplotlib solo para dibujar el PNG.

import os
import numpy as np

import matplotlib
matplotlib.use("Agg")  # sin ventana, solo guarda a archivo
import matplotlib.pyplot as plt


def guardar_png(frame, tipo, camara, ruta):
    """Guarda un PNG con la figura 28x28 y la etiqueta reconocida encima."""
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    img = frame[0] if frame.ndim == 3 else frame  # (28,28)

    fig, ax = plt.subplots(figsize=(2.6, 2.6), dpi=100)
    ax.imshow(img, cmap="gray_r", vmin=0, vmax=1)
    ax.set_xticks([]); ax.set_yticks([])
    # caja + etiqueta estilo "Detecto: X"
    for spine in ax.spines.values():
        spine.set_edgecolor("#f47216")
        spine.set_linewidth(3)
    ax.set_title(f"Detected: {tipo}", color="#2a9d4e", fontsize=13, fontweight="bold")
    ax.text(0.02, 0.96, camara, transform=ax.transAxes, fontsize=8,
            color="#2c7fb8", va="top")
    fig.tight_layout(pad=0.4)
    fig.savefig(ruta, bbox_inches="tight")
    plt.close(fig)


def hoja_contacto(frames, tipos, camaras, ruta, cols=5):
    """Arma una sola imagen con varias detecciones (util para 1 sola foto)."""
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    n = len(frames)
    filas = (n + cols - 1) // cols
    fig, axes = plt.subplots(filas, cols, figsize=(cols * 1.8, filas * 1.9), dpi=100)
    axes = np.array(axes).reshape(-1)
    for i in range(len(axes)):
        ax = axes[i]
        ax.set_xticks([]); ax.set_yticks([])
        if i < n:
            img = frames[i][0] if frames[i].ndim == 3 else frames[i]
            ax.imshow(img, cmap="gray_r", vmin=0, vmax=1)
            for spine in ax.spines.values():
                spine.set_edgecolor("#f47216"); spine.set_linewidth(2)
            ax.set_title(f"{tipos[i]}", color="#2a9d4e", fontsize=9, fontweight="bold")
            ax.text(0.03, 0.95, camaras[i], transform=ax.transAxes, fontsize=6,
                    color="#2c7fb8", va="top")
        else:
            ax.axis("off")
    fig.suptitle("AI recognition detections", fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(ruta, bbox_inches="tight")
    plt.close(fig)
