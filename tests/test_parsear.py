import numpy as np
import pytest

from datos.encuestas.parsear import _filas, _num, autonomicas, nacionales
from datos.encuestas.descargar_historicas import extraer_tsv


def test_num_distingue_millares_decimales_y_cotas():
    assert _num("1,200") == 1200
    assert _num("4,9") == 4.9
    assert _num("<1.0") == 0.5
    assert np.isnan(_num("?"))


def test_fila_con_columnas_desalineadas_falla_de_forma_visible():
    cabecera = ["firma", "fecha", "n", "participación", "PP"]
    linea = "Casa\t11 Oct 2026\t1000\t70\t30\textra"
    with pytest.raises(ValueError, match="columnas"):
        _filas("", "2026", "España", cabecera, [linea], anio_col=False)


def test_los_raw_actuales_se_parsean_y_tienen_fechas():
    nac = nacionales()
    aut = autonomicas()
    assert len(nac) > 1100 and len(aut) > 90
    assert {"2015", "2016", "2019A", "2019N", "2023", "2026"} <= set(nac.ciclo)
    assert nac.loc[nac.tipo == "encuesta", ["inicio", "fin"]].notna().all().all()
    assert aut.loc[aut.tipo == "encuesta", ["inicio", "fin"]].notna().all().all()

    resultados = nac[nac.tipo == "resultado"].set_index(["ciclo", "encuestadora"])
    assert resultados.loc[("2015", "2015 general election"), "PP"] == 28.7
    assert resultados.loc[("2016", "2016 general election"), "PODEMOS"] == 21.2
    assert resultados.loc[("2019A", "April 2019 general election"), "VOX"] == 10.3


def test_descargador_expande_rowspan_sin_red():
    html = """
    <table class="wikitable">
      <tr><th>Polling firm/Commissioner</th><th>Fieldwork date</th><th>Sample size</th>
          <th>Turnout</th><th><img alt="PP"></th><th>Lead</th></tr>
      <tr><td rowspan="2">Casa</td><td rowspan="2">1 Jan</td><td rowspan="2">1,000</td>
          <td>70</td><td>30</td><td>10</td></tr>
      <tr><td>71</td><td>31</td><td>9</td></tr>
      <tr><td>Otra</td><td>2 Jan</td><td>900</td><td>69</td><td>29</td><td>8</td></tr>
      <tr><td>Tercera</td><td>3 Jan</td><td>800</td><td>68</td><td>28</td><td>7</td></tr>
      <tr><td>Cuarta</td><td>4 Jan</td><td>700</td><td>67</td><td>27</td><td>6</td></tr>
      <tr><td>Quinta</td><td>5 Jan</td><td>600</td><td>66</td><td>26</td><td>5</td></tr>
      <tr><td>Sexta</td><td>6 Jan</td><td>500</td><td>65</td><td>25</td><td>4</td></tr>
      <tr><td>Séptima</td><td>7 Jan</td><td>400</td><td>64</td><td>24</td><td>3</td></tr>
      <tr><td>Octava</td><td>8 Jan</td><td>300</td><td>63</td><td>23</td><td>2</td></tr>
      <tr><td>Novena</td><td>9 Jan</td><td>200</td><td>62</td><td>22</td><td>1</td></tr>
      <tr><td>Décima</td><td>10 Jan</td><td>100</td><td>61</td><td>21</td><td>0</td></tr>
      <tr><td>Once</td><td>11 Jan</td><td>100</td><td>60</td><td>20</td><td>0</td></tr>
      <tr><td>Doce</td><td>12 Jan</td><td>100</td><td>59</td><td>19</td><td>0</td></tr>
      <tr><td>Trece</td><td>13 Jan</td><td>100</td><td>58</td><td>18</td><td>0</td></tr>
      <tr><td>Catorce</td><td>14 Jan</td><td>100</td><td>57</td><td>17</td><td>0</td></tr>
      <tr><td>Quince</td><td>15 Jan</td><td>100</td><td>56</td><td>16</td><td>0</td></tr>
      <tr><td>Dieciséis</td><td>16 Jan</td><td>100</td><td>55</td><td>15</td><td>0</td></tr>
      <tr><td>Diecisiete</td><td>17 Jan</td><td>100</td><td>54</td><td>14</td><td>0</td></tr>
      <tr><td>Dieciocho</td><td>18 Jan</td><td>100</td><td>53</td><td>13</td><td>0</td></tr>
      <tr><td>Diecinueve</td><td>19 Jan</td><td>100</td><td>52</td><td>12</td><td>0</td></tr>
    </table>
    """
    filas = extraer_tsv(html, 2015, ("PP",)).splitlines()
    assert filas[1].split("\t")[:4] == ["2015", "Casa", "1 Jan", "1,000"]
    assert filas[2].split("\t")[:4] == ["2015", "Casa", "1 Jan", "1,000"]

