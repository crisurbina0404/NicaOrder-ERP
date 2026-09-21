/**
 * NicaOrder - Scripts de paginas de autenticacion (login / registro)
 * Incluye: mostrar/ocultar contrasena y transicion animada entre paginas.
 */

// ===== Mostrar / ocultar contrasena =====

function togglePassword(btn, inputId) {
    var input = document.getElementById(inputId);
    var icon = btn.querySelector('.material-icons-outlined');
    var show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    icon.textContent = show ? 'visibility_off' : 'visibility';
    btn.setAttribute('aria-label', show ? 'Ocultar contrasena' : 'Mostrar contrasena');
}

// ===== Transicion animada entre login y registro =====

(function () {
    'use strict';

    var LEAVE_CLASS = 'is-leaving';
    var LEAVE_DELAY_MS = 220;
    var AUTH_ROUTES = ['/auth/login', '/auth/register'];

    function isAuthRoute(href) {
        return AUTH_ROUTES.some(function (route) {
            return href === route || href.indexOf(route + '?') === 0;
        });
    }

    document.addEventListener('click', function (e) {
        var link = e.target.closest ? e.target.closest('a[href]') : null;
        if (!link) return;

        var href = link.getAttribute('href');

        // Solo anima la navegacion entre paginas de autenticacion
        if (!isAuthRoute(href)) return;
        if (document.body.classList.contains(LEAVE_CLASS)) return;

        e.preventDefault();
        document.body.classList.add(LEAVE_CLASS);

        setTimeout(function () {
            window.location.href = href;
        }, LEAVE_DELAY_MS);
    });
})();
