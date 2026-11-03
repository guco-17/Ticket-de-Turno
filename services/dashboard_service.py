from extensions import db
from models import Estatus, Municipio, Solicitud


class DashboardService:
    """Servicio orientado a objetos para calcular métricas y gráficas del tablero mediante el ORM."""

    def obtener_estadisticas(self, municipio_id: int | None = None) -> dict:
        municipio_filtrado = None
        if municipio_id is not None:
            municipio_filtrado = db.session.get(Municipio, municipio_id)
            if municipio_filtrado is None:
                raise LookupError("El municipio seleccionado no existe.")

        estatus_list = Estatus.query.order_by(Estatus.id).all()
        municipios_list = Municipio.query.order_by(Municipio.nombre).all()

        # Conteo por estatus aplicando el filtro de municipio (o total si es None)
        conteo_estatus_query = db.session.query(
            Solicitud.estatus_id,
            db.func.count(Solicitud.id),
        )
        if municipio_filtrado is not None:
            conteo_estatus_query = conteo_estatus_query.filter(
                Solicitud.municipio_id == municipio_filtrado.id
            )
        conteos_por_estatus_id = dict(
            conteo_estatus_query.group_by(Solicitud.estatus_id).all()
        )

        por_estatus = []
        pendientes = 0
        resueltos = 0
        otros = 0

        for est in estatus_list:
            cantidad = int(conteos_por_estatus_id.get(est.id, 0))
            por_estatus.append(
                {
                    "id": est.id,
                    "nombre": est.nombre,
                    "total": cantidad,
                }
            )
            if est.nombre == "Pendiente":
                pendientes += cantidad
            elif est.nombre == "Resuelto":
                resueltos += cantidad
            else:
                otros += cantidad

        total = pendientes + resueltos + otros
        porcentaje_resuelto = round((resueltos / total) * 100, 1) if total > 0 else 0.0

        # Desglose por municipio y estatus para gráficas comparativas
        filas_municipio_estatus = (
            db.session.query(
                Solicitud.municipio_id,
                Estatus.nombre,
                db.func.count(Solicitud.id),
            )
            .join(Estatus, Solicitud.estatus_id == Estatus.id)
            .group_by(Solicitud.municipio_id, Estatus.nombre)
            .all()
        )
        mapa_municipio: dict[int, dict[str, int]] = {}
        for mun_id, est_nombre, cantidad in filas_municipio_estatus:
            bucket = mapa_municipio.setdefault(
                mun_id,
                {"Pendiente": 0, "Resuelto": 0, "Otros": 0},
            )
            if est_nombre in ("Pendiente", "Resuelto"):
                bucket[est_nombre] += int(cantidad)
            else:
                bucket["Otros"] += int(cantidad)

        por_municipio = []
        for mun in municipios_list:
            if municipio_filtrado is not None and mun.id != municipio_filtrado.id:
                continue
            datos_mun = mapa_municipio.get(
                mun.id,
                {"Pendiente": 0, "Resuelto": 0, "Otros": 0},
            )
            total_mun = (
                datos_mun["Pendiente"] + datos_mun["Resuelto"] + datos_mun["Otros"]
            )
            por_municipio.append(
                {
                    "id": mun.id,
                    "nombre": mun.nombre,
                    "activo": bool(mun.activo),
                    "pendientes": datos_mun["Pendiente"],
                    "resueltos": datos_mun["Resuelto"],
                    "otros": datos_mun["Otros"],
                    "total": total_mun,
                }
            )

        return {
            "filtro": {
                "municipio_id": municipio_filtrado.id if municipio_filtrado else None,
                "municipio_nombre": (
                    municipio_filtrado.nombre
                    if municipio_filtrado
                    else "Todos los municipios (Total)"
                ),
            },
            "resumen": {
                "total": total,
                "pendientes": pendientes,
                "resueltos": resueltos,
                "otros": otros,
                "porcentaje_resuelto": porcentaje_resuelto,
            },
            "por_estatus": por_estatus,
            "por_municipio": por_municipio,
            "municipios": [mun.to_dict() for mun in municipios_list],
        }

