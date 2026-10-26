document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('#solicitud-form');
    const searchForm = document.querySelector('#buscar-solicitud-form');
    const fields = form.querySelectorAll('input:not([type="hidden"]), select');
    const statusMessage = document.querySelector('#mensaje-formulario');
    const searchMessage = document.querySelector('#mensaje-busqueda');
    const submitButton = document.querySelector('#guardar-solicitud');
    const cancelEditButton = document.querySelector('#cancelar-edicion');
    const currentTurn = document.querySelector('#turno-actual');
    const turnBadge = document.querySelector('#turno-badge');
    const formDescription = document.querySelector('#form-description');
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
    const fieldNames = [
        'curp',
        'nombre',
        'primer_apellido',
        'segundo_apellido',
        'telefono_contacto',
        'correo',
        'municipio',
        'nivel_educativo',
        'asunto'
    ];

    const isFieldValid = (field) => {
        const value = field.value.trim();

        if (value === '') {
            return false;
        }

        switch (field.id) {
            case 'curp':
            case 'curp-busqueda':
                return /^[A-Z][AEIOU][A-Z]{2}\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[HM](AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)[B-DF-HJ-NP-TV-Z]{3}[A-Z0-9]\d$/i.test(value);
            case 'nombre':
            case 'primer-apellido':
            case 'segundo-apellido':
                return /^[\p{L}]+(?:[ '\u2019-][\p{L}]+)*$/u.test(value);
            case 'telefono-contacto':
                return /^\d{10}$/.test(value.replace(/[\s()-]/g, ''));
            case 'correo':
                return field.validity.valid;
            default:
                return true;
        }
    };

    const validateField = (field) => {
        const valid = isFieldValid(field);
        field.classList.toggle('input-valid', valid);
        field.classList.toggle('input-error', !valid);
        return valid;
    };

    const showMessage = (element, message, type) => {
        element.textContent = message;
        element.className = type ? `turno-mensaje ${type}` : '';
        element.hidden = !message;
    };

    const setEditMode = (enabled, turn = '') => {
        currentTurn.value = enabled ? String(turn) : '';
        form.elements.curp.readOnly = enabled;
        turnBadge.textContent = enabled ? `Turno actual: ${turn}` : '';
        turnBadge.hidden = !enabled;
        formDescription.textContent = enabled
            ? 'Modifica los datos y guarda los cambios. Se descargará un comprobante actualizado.'
            : 'Completa los datos para registrar una solicitud y descargar su comprobante.';
        submitButton.textContent = enabled
            ? 'Guardar cambios y descargar comprobante'
            : 'Registrar solicitud y descargar comprobante';
        cancelEditButton.hidden = !enabled;
        showMessage(statusMessage, '', '');
    };

    const downloadReceipt = (blob, turn) => {
        const downloadUrl = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `comprobante-turno-${turn}.pdf`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
    };

    fields.forEach((field) => {
        const eventName = field.tagName === 'SELECT' ? 'change' : 'input';
        field.addEventListener(eventName, () => validateField(field));
        field.addEventListener('blur', () => validateField(field));
    });

    searchForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        const curpInput = document.querySelector('#curp-busqueda');
        const turnInput = document.querySelector('#turno-busqueda');
        const curp = curpInput.value.trim().toUpperCase();
        const turn = Number(turnInput.value);

        if (!isFieldValid({ id: 'curp-busqueda', value: curp }) || !Number.isInteger(turn) || turn < 1) {
            showMessage(searchMessage, 'Captura un CURP válido y un número de turno positivo.', 'error');
            return;
        }

        const searchButton = searchForm.querySelector('button[type="submit"]');
        searchButton.disabled = true;
        showMessage(searchMessage, 'Buscando solicitud…', '');

        try {
            const response = await fetch('/buscar-solicitud', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify({ curp, turno: turn })
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.mensaje || 'No se encontró la solicitud.');
            }

            for (const name of fieldNames) {
                form.elements[name].value = result[name];
                validateField(form.elements[name]);
            }
            setEditMode(true, result.turno);
            showMessage(searchMessage, 'Solicitud encontrada. Puedes modificar sus datos.', 'success');
            form.scrollIntoView({ behavior: 'smooth', block: 'start' });
        } catch (error) {
            showMessage(searchMessage, error.message || 'No se pudo consultar la solicitud.', 'error');
        } finally {
            searchButton.disabled = false;
        }
    });

    cancelEditButton.addEventListener('click', () => {
        form.reset();
        fields.forEach((field) => {
            field.classList.remove('input-valid', 'input-error');
        });
        setEditMode(false);
        showMessage(searchMessage, '', '');
        form.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const isValid = Array.from(fields).map(validateField).every(Boolean);

        if (!isValid) {
            showMessage(statusMessage, 'Revisa los campos marcados antes de continuar.', 'error');
            return;
        }

        submitButton.disabled = true;
        cancelEditButton.disabled = true;
        showMessage(statusMessage, 'Guardando la solicitud…', '');

        try {
            const datos = Object.fromEntries(new FormData(form));
            const response = await fetch('/generar-turno', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken
                },
                body: JSON.stringify(datos)
            });

            if (!response.ok) {
                const result = await response.json();
                throw new Error(result.mensaje || 'No se pudo guardar la solicitud.');
            }

            const turn = response.headers.get('X-Turno-Asignado');
            const wasUpdated = response.headers.get('X-Registro-Actualizado') === 'true';
            const receipt = await response.blob();
            downloadReceipt(receipt, turn);
            showMessage(
                statusMessage,
                wasUpdated
                    ? `La solicitud fue modificada. Se descargó el comprobante actualizado del turno ${turn}.`
                    : `La solicitud quedó registrada con el turno ${turn}. Se descargó su comprobante PDF.`,
                'success'
            );
            setEditMode(true, turn);
        } catch (error) {
            showMessage(statusMessage, error.message || 'No se pudo conectar con el servidor.', 'error');
        } finally {
            submitButton.disabled = false;
            cancelEditButton.disabled = false;
        }
    });
});
