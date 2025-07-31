// /static/js/menu.js - FIXED VERSION

document.addEventListener("DOMContentLoaded", function () {
  const toggleBtn = document.getElementById("menu-toggle-btn");
  const dropdown = document.getElementById("menu-dropdown");

  if (toggleBtn && dropdown) {
    toggleBtn.addEventListener("click", function () {
      dropdown.classList.toggle("open");
    });

    window.addEventListener("click", function (e) {
      // Don't close menu if clicking RTMP Tweak button or Services button
      if (e.target.id === "tweak-popup-btn" || e.target.id === "services-popup-btn") {
        return;
      }
      if (!dropdown.contains(e.target) && e.target !== toggleBtn) {
        dropdown.classList.remove("open");
      }
    });
  }
});

document.addEventListener("DOMContentLoaded", () => {
  const currentPath = window.location.pathname;

  // Set active page highlighting
  if (currentPath === "/dashboard" || currentPath === "/") {
    const dashboardLink = document.querySelector('#menu-dropdown a[href="/dashboard"]');
    if (dashboardLink) {
      dashboardLink.classList.add("active-page");
    }
  } else if (currentPath === "/event_details") {
    const eventLink = document.querySelector('#menu-dropdown a[href="/event_details"]');
    if (eventLink) {
      eventLink.classList.add("active-page");
    }
  } else if (currentPath === "/advertising") {
    const adLink = document.querySelector('#menu-dropdown a[href="/advertising"]');
    if (adLink) {
      adLink.classList.add("active-page");
    }
  } else if (currentPath === "/mixer") {
    const mixerLink = document.querySelector('#menu-dropdown a[href="/mixer"]');
    if (mixerLink) {
      mixerLink.classList.add("active-page");
    }
  } else if (currentPath === "/analytics") {
    const analyticsLink = document.querySelector('#menu-dropdown a[href="/analytics"]');
    if (analyticsLink) {
      analyticsLink.classList.add("active-page");
    }
  } else if (currentPath === "/preview_scenes") {
    const previewLink = document.querySelector('#menu-dropdown a[href="/preview_scenes"]');
    if (previewLink) {
      previewLink.classList.add("active-page");
    }
  } else if (currentPath === "/logs") {
    const logsLink = document.querySelector('#menu-dropdown a[href="/logs"]');
    if (logsLink) {
      logsLink.classList.add("active-page");
    }
  }
});