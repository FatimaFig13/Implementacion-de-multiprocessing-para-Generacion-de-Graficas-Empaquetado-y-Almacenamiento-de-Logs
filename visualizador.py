import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from fuente_datos import PrepararDatos

class Vizualizador:

    def __init__(self, fuente: PrepararDatos):
        self.fuente = fuente
 
    # ---- Punto de entrada generico -----------------------------------------
 
    def graficar(self, mostrar=True, guardar=False, nombre_archivo="grafica.png"):
        if self.fuente.esta_cargando():
            print("Cargando datos... por favor espere.")
            return None
 
        if self.fuente.esta_en_error() or self.fuente.df is None:
            print(f"No se pudo generar la grafica. {self.fuente.error or 'Sin datos disponibles.'}")
            return None
 
        meta = self.fuente.metadatos
        tipo = meta.get("tipo_grafico", "barras_agrupadas")
 
        despachador = {
            "barras_agrupadas": self._grafica_barras_agrupadas,
            "lineas": self._grafica_lineas,
            "pastel": self._grafica_pastel,
            "dispersion": self._grafica_dispersion,
            "histograma": self._grafica_histograma,
            "boxplot": self._grafica_boxplot,
        }
 
        if tipo not in despachador:
            print(f"Tipo de grafico '{tipo}' no soportado. Opciones: {list(despachador)}")
            return None
 
        fig = despachador[tipo](meta)
        if fig is None:
            return None
 
        if guardar:
            self._guardar(fig, meta.get("nombre_archivo", nombre_archivo))
        if mostrar:
            plt.show()
        else:
            plt.close(fig)
        return fig
 
    # ---- Preparacion de datos segun filtros/orden de los metadatos --------
 
    def _preparar(self, columnas, meta, columnas_numericas=None):
        df = self.fuente.df
        faltantes = [c for c in columnas if c and c not in df.columns]
        if faltantes:
            raise KeyError(f"Columnas no encontradas en los datos de la API: {faltantes}")
 
        data = df.copy()
        filtros = meta.get("filtros")
        if filtros:
            mask = pd.Series(True, index=data.index)
            for col, val in filtros.items():
                if isinstance(val, (list, tuple, set)):
                    mask &= data[col].isin(val)
                else:
                    mask &= data[col] == val
            data = data[mask]
 
        columnas_validas = [c for c in columnas if c]
        data = data[columnas_validas].copy()
 
        for col in (columnas_numericas or []):
            data[col] = pd.to_numeric(data[col], errors="coerce")
 
        ordenar_por = meta.get("ordenar_por")
        if ordenar_por and ordenar_por in data.columns:
            data = data.sort_values(ordenar_por)
 
        if data.empty:
            raise ValueError("El filtro aplicado no arrojo ninguna fila.")
 
        return data.reset_index(drop=True)
 
    # ---- Tipos de grafico soportados ----------------------------------------
 
    def _grafica_barras_agrupadas(self, meta):
        columna_x = meta["columna_x"]
        columna_y = meta["columna_y"]
        columna_grupo = meta.get("columna_grupo")
        columnas = [columna_x, columna_y, columna_grupo]
 
        try:
            data = self._preparar(columnas, meta, columnas_numericas=[columna_y])
        except (KeyError, ValueError) as e:
            print(f"No se pudo generar la grafica: {e}")
            return None
 
        figsize = tuple(meta.get("figsize", (14, 6)))
        fig, ax = plt.subplots(figsize=figsize)
        sns.barplot(
            data=data, x=columna_x, y=columna_y, hue=columna_grupo,
            palette=meta.get("paleta"), ax=ax, errorbar=None
        )
        ax.set_title(meta.get("titulo", ""), fontsize=13, fontweight="bold", pad=14)
        ax.set_xlabel(meta.get("etiqueta_x", columna_x), fontsize=11)
        ax.set_ylabel(meta.get("etiqueta_y", columna_y), fontsize=11)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=9)
        if columna_grupo:
            ax.legend(title=columna_grupo)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.spines[["top", "right"]].set_visible(False)
        plt.tight_layout()
        return fig
 
    def _grafica_lineas(self, meta):
        columna_x = meta["columna_x"]
        columna_y = meta["columna_y"]
        columna_grupo = meta.get("columna_grupo")
        columnas = [columna_x, columna_y, columna_grupo]
 
        try:
            data = self._preparar(columnas, meta, columnas_numericas=[columna_y])
        except (KeyError, ValueError) as e:
            print(f"No se pudo generar la grafica: {e}")
            return None
 
        figsize = tuple(meta.get("figsize", (12, 6)))
        fig, ax = plt.subplots(figsize=figsize)
        sns.lineplot(
            data=data, x=columna_x, y=columna_y, hue=columna_grupo,
            palette=meta.get("paleta"), ax=ax, marker="o"
        )
        ax.set_title(meta.get("titulo", ""), fontsize=13, fontweight="bold", pad=14)
        ax.set_xlabel(meta.get("etiqueta_x", columna_x), fontsize=11)
        ax.set_ylabel(meta.get("etiqueta_y", columna_y), fontsize=11)
 
        rango_y = meta.get("rango_y")
        if rango_y:
            ax.set_ylim(rango_y[0], rango_y[1])
 
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.spines[["top", "right"]].set_visible(False)
        plt.tight_layout()
        return fig
 
    def _grafica_pastel(self, meta):
        columna_categoria = meta["columna_categoria"]
        columna_valor = meta["columna_valor"]
        agregacion = meta.get("agregacion", "sum")
 
        try:
            data = self._preparar(
                [columna_categoria, columna_valor, None],
                meta, columnas_numericas=[columna_valor]
            )
        except (KeyError, ValueError) as e:
            print(f"No se pudo generar la grafica: {e}")
            return None
 
        resumen = data.groupby(columna_categoria)[columna_valor].agg(agregacion)
 
        figsize = tuple(meta.get("figsize", (8, 8)))
        fig, ax = plt.subplots(figsize=figsize)
        colores = sns.color_palette(meta.get("paleta"), n_colors=len(resumen))
        ax.pie(
            resumen.values, labels=resumen.index, autopct="%1.1f%%",
            colors=colores, startangle=90
        )
        ax.set_title(meta.get("titulo", ""), fontsize=13, fontweight="bold", pad=14)
        plt.tight_layout()
        return fig
 
    def _grafica_dispersion(self, meta):
        columna_x = meta["columna_x"]
        columna_y = meta["columna_y"]
        columna_grupo = meta.get("columna_grupo")
        columnas = [columna_x, columna_y, columna_grupo]
 
        try:
            data = self._preparar(columnas, meta, columnas_numericas=[columna_x, columna_y])
        except (KeyError, ValueError) as e:
            print(f"No se pudo generar la grafica: {e}")
            return None
 
        figsize = tuple(meta.get("figsize", (10, 6)))
        fig, ax = plt.subplots(figsize=figsize)
        sns.scatterplot(
            data=data, x=columna_x, y=columna_y, hue=columna_grupo,
            palette=meta.get("paleta"), ax=ax, s=60, alpha=0.8
        )
        ax.set_title(meta.get("titulo", ""), fontsize=13, fontweight="bold", pad=14)
        ax.set_xlabel(meta.get("etiqueta_x", columna_x), fontsize=11)
        ax.set_ylabel(meta.get("etiqueta_y", columna_y), fontsize=11)
        ax.grid(linestyle="--", alpha=0.4)
        ax.spines[["top", "right"]].set_visible(False)
        plt.tight_layout()
        return fig
 
    def _grafica_histograma(self, meta):
        columna_x = meta["columna_x"]
        columna_grupo = meta.get("columna_grupo")
        bins = meta.get("bins", 20)
        columnas = [columna_x, columna_grupo, None]
 
        try:
            data = self._preparar(columnas, meta, columnas_numericas=[columna_x])
        except (KeyError, ValueError) as e:
            print(f"No se pudo generar la grafica: {e}")
            return None
 
        figsize = tuple(meta.get("figsize", (10, 6)))
        fig, ax = plt.subplots(figsize=figsize)
        sns.histplot(
            data=data, x=columna_x, hue=columna_grupo, bins=bins,
            palette=meta.get("paleta"), ax=ax, kde=meta.get("kde", False)
        )
        ax.set_title(meta.get("titulo", ""), fontsize=13, fontweight="bold", pad=14)
        ax.set_xlabel(meta.get("etiqueta_x", columna_x), fontsize=11)
        ax.set_ylabel(meta.get("etiqueta_y", "Frecuencia"), fontsize=11)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.spines[["top", "right"]].set_visible(False)
        plt.tight_layout()
        return fig
 
    def _grafica_boxplot(self, meta):
        columna_x = meta["columna_x"]
        columna_y = meta["columna_y"]
        columna_grupo = meta.get("columna_grupo")
        columnas = [columna_x, columna_y, columna_grupo]
 
        try:
            data = self._preparar(columnas, meta, columnas_numericas=[columna_y])
        except (KeyError, ValueError) as e:
            print(f"No se pudo generar la grafica: {e}")
            return None
 
        figsize = tuple(meta.get("figsize", (12, 6)))
        fig, ax = plt.subplots(figsize=figsize)
        sns.boxplot(
            data=data, x=columna_x, y=columna_y, hue=columna_grupo,
            palette=meta.get("paleta"), ax=ax
        )
        ax.set_title(meta.get("titulo", ""), fontsize=13, fontweight="bold", pad=14)
        ax.set_xlabel(meta.get("etiqueta_x", columna_x), fontsize=11)
        ax.set_ylabel(meta.get("etiqueta_y", columna_y), fontsize=11)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.spines[["top", "right"]].set_visible(False)
        plt.tight_layout()
        return fig
 
    # ---- Guardado -------------------------------------------------------------
 
    def _guardar(self, fig, nombre_archivo):
        directorio = os.path.dirname(nombre_archivo)
        if directorio and not os.path.isdir(directorio):
            os.makedirs(directorio, exist_ok=True)
        try:
            fig.savefig(nombre_archivo, dpi=150, bbox_inches="tight")
            print(f"Grafica guardada como: {nombre_archivo}")
        except Exception as e:
            print(f"No se pudo guardar la grafica en '{nombre_archivo}': {e}")