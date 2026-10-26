document.addEventListener('DOMContentLoaded', () => {
    const form = document.querySelector('form');
    const fields = form.querySelectorAll('input, select');
    const statusMessage = document.querySelector('#mensaje-formulario');
    const submitButton = form.querySelector('button[type="submit"]');

    const isFieldValid = (field) => {
        const value = field.value.trim();

        if (value === '') {
            return false;
        }

        switch (field.id) {
            case 'curp':
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

    fields.forEach((field) => {
        const eventName = field.tagName === 'SELECT' ? 'change' : 'input';
        field.addEventListener(eventName, () => validateField(field));
        field.addEventListener('blur', () => validateField(field));
    });

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const isValid = Array.from(fields).map(validateField).every(Boolean);

        if (!isValid) {
            alert('Revisa los campos marcados en rojo.');
            return;
        }

        submitButton.disabled = true;
        statusMessage.hidden = true;

        try {
            const datos = Object.fromEntries(new FormData(form));
            const response = await fetch('/generar-turno', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(datos)
            });
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.mensaje || 'No se pudieron cargar los datos.');
            }

            statusMessage.textContent = result.mensaje;
            statusMessage.className = 'turno-mensaje success';
            alert(`${result.mensaje}\n\nCURP: ${datos.curp}\nNombre: ${datos.nombre} ${datos.primer_apellido} ${datos.segundo_apellido}\nTeléfono: ${datos.telefono_contacto}\nCorreo: ${datos.correo}\nMunicipio: ${datos.municipio}\nNivel educativo: ${datos.nivel_educativo}\nAsunto: ${datos.asunto}`);
        } catch (error) {
            statusMessage.textContent = error.message || 'No se pudo conectar con el servidor.';
            statusMessage.className = 'turno-mensaje error';
        } finally {
            statusMessage.hidden = false;
            submitButton.disabled = false;
        }
    });
});