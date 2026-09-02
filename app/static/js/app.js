document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.getElementById("sidebarToggle");
    var body = document.body;

    if (toggle) {
        toggle.addEventListener("click", function () {
            if (window.innerWidth <= 768) {
                body.classList.toggle("sidebar-open");
            } else {
                body.classList.toggle("sidebar-collapsed");
            }
        });
    }

    document.addEventListener("click", function (e) {
        if (body.classList.contains("sidebar-open")) {
            var sidebar = document.getElementById("sidebar");
            if (sidebar && !sidebar.contains(e.target) && e.target !== toggle) {
                body.classList.remove("sidebar-open");
            }
        }
    });

    var flashes = document.querySelectorAll(".flash");
    flashes.forEach(function (flash) {
        setTimeout(function () {
            flash.style.opacity = "0";
            flash.style.transform = "translateY(-8px)";
            setTimeout(function () {
                flash.remove();
            }, 200);
        }, 4000);
    });

    function updateClock() {
        var now = new Date();
        var hours = String(now.getHours()).padStart(2, "0");
        var minutes = String(now.getMinutes()).padStart(2, "0");
        var seconds = String(now.getSeconds()).padStart(2, "0");
        var timeEl = document.getElementById("clockTime");
        if (timeEl) timeEl.textContent = hours + ":" + minutes + ":" + seconds;

        var days = ["Domingo", "Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado"];
        var months = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
        var dateStr = days[now.getDay()] + " " + now.getDate() + " " + months[now.getMonth()] + " " + now.getFullYear();
        var dateEl = document.getElementById("clockDate");
        if (dateEl) dateEl.textContent = dateStr;

        var h = now.getHours();
        var greeting = h < 12 ? "Buenos dias" : h < 18 ? "Buenas tardes" : "Buenas noches";
        var greetEl = document.getElementById("sidebarGreeting");
        if (greetEl) greetEl.textContent = greeting + ", " + (document.querySelector(".user-name") ? document.querySelector(".user-name").textContent.split(" ")[0] : "");
    }

    updateClock();
    setInterval(updateClock, 1000);

    var navGroups = document.querySelectorAll(".nav-group");
    navGroups.forEach(function (group) {
        var parentItem = group.querySelector(".nav-item");
        if (parentItem) {
            parentItem.addEventListener("click", function (e) {
                e.preventDefault();
                group.classList.toggle("open");
            });
        }
    });

    var activeChild = document.querySelector(".nav-child.active");
    if (activeChild) {
        var parentGroup = activeChild.closest(".nav-group");
        if (parentGroup) parentGroup.classList.add("open");
    }

    document.querySelectorAll("form").forEach(function (form) {
        form.addEventListener("submit", function () {
            var btn = form.querySelector('[type="submit"]');
            if (btn && !btn.disabled) {
                btn.disabled = true;
                btn.style.opacity = "0.6";
                var originalText = btn.innerHTML;
                btn.dataset.originalHtml = originalText;
                btn.innerHTML = '<span class="material-icons-outlined" style="animation:spin 1s linear infinite">sync</span> Procesando...';
            }
        });
    });

    document.querySelectorAll("form[novalidate]").forEach(function (form) {
        form.addEventListener("submit", function (e) {
            var valid = true;
            form.querySelectorAll("[required]").forEach(function (input) {
                var group = input.closest(".form-group");
                if (!input.value.trim()) {
                    valid = false;
                    if (group) group.classList.add("error");
                } else {
                    if (group) group.classList.remove("error");
                }
            });
            if (!valid) {
                e.preventDefault();
                var btn = form.querySelector('[type="submit"]');
                if (btn) {
                    btn.disabled = false;
                    btn.style.opacity = "1";
                    btn.innerHTML = btn.dataset.originalHtml || btn.innerHTML;
                }
            }
        });
    });
});
