document.addEventListener("DOMContentLoaded", () => {
  const grid = document.getElementById("user-grid");
  if (!grid) return;

  const filterSelect = document.getElementById("team-filter");
  if (!filterSelect) return;

  // Show controls (progressive enhancement)
  const controls = document.querySelector(".header-controls");
  if (controls) controls.style.display = "flex";

  // Store initial cards
  const initialCards = Array.from(document.querySelectorAll(".user-card"));

  function filterByTeam(selectedTeam) {
    // Update select if needed (e.g. from back button or link click)
    if (filterSelect.value !== selectedTeam) {
      filterSelect.value = selectedTeam;
    }

    // Clear grid
    grid.innerHTML = "";

    if (selectedTeam === "all") {
      // Restore all cards, sorted by name
      initialCards.sort((a, b) => a.dataset.name.localeCompare(b.dataset.name));
      initialCards.forEach((card) => {
        card.classList.remove("hidden-card"); // Ensure server-hidden cards are shown
        card.style.display = "block";
        grid.appendChild(card);
      });
      return;
    }

    // Filter and Section
    const leads = [];
    const members = [];

    initialCards.forEach((card) => {
      const teams = JSON.parse(card.dataset.teams);
      const teamInfo = teams.find((t) => t.team_name === selectedTeam);

      if (teamInfo) {
        card.classList.remove("hidden-card");
        card.style.display = "block";
        if (teamInfo.is_lead) {
          leads.push(card);
        } else {
          members.push(card);
        }
      } else {
        card.style.display = "none";
      }
    });

    // Sort each group
    leads.sort((a, b) => a.dataset.name.localeCompare(b.dataset.name));
    members.sort((a, b) => a.dataset.name.localeCompare(b.dataset.name));

    // Append with Headers
    if (leads.length > 0) {
      const header = document.createElement("h2");
      header.className = "grid-header";
      header.textContent = "Team Leads";
      grid.appendChild(header);
      leads.forEach((card) => grid.appendChild(card));
    }

    if (members.length > 0) {
      const header = document.createElement("h2");
      header.className = "grid-header";
      header.textContent = "Team Members";
      grid.appendChild(header);
      members.forEach((card) => grid.appendChild(card));
    }

    if (leads.length === 0 && members.length === 0) {
      const msg = document.createElement("div");
      msg.textContent = "No active members found in this team.";
      msg.className = "empty-message";
      grid.appendChild(msg);
    }
  }

  // Initial state from URL
  const updateStateFromUrl = () => {
    const path = window.location.pathname;
    let team = "all";
    if (path.startsWith("/team/")) {
      team = decodeURIComponent(path.substring(6));
    }
    // Set the dropdown initially without re-filtering if it matches (optimization),
    // but for simplicity and correctness (to handle browser back/forward), running logic is safer.
    // However, on initial load, the server already rendered the correct state.
    // So we only update the dropdown.
    if (filterSelect.value !== team) {
      filterSelect.value = team;
    }
  };

  updateStateFromUrl();

  // Event Listeners
  filterSelect.addEventListener("change", function (e) {
    const selectedTeam = e.target.value;
    const newUrl = selectedTeam === "all"
      ? "/"
      : `/team/${encodeURIComponent(selectedTeam)}`;
    history.pushState({ team: selectedTeam }, "", newUrl);
    filterByTeam(selectedTeam);
  });

  // Handle Back/Forward
  window.addEventListener("popstate", (e) => {
    const path = window.location.pathname;
    let team = "all";
    if (path.startsWith("/team/")) {
      team = decodeURIComponent(path.substring(6));
    }
    filterByTeam(team);
  });

  // Handle Team Chip Clicks
  document.addEventListener("click", (e) => {
    // Check if clicked element or parent is a .js-team-filter
    const link = e.target.closest(".js-team-filter");
    if (link) {
      e.preventDefault();
      // href is /team/<name>
      const href = link.getAttribute("href");
      const teamName = decodeURIComponent(href.substring(6)); // strip /team/

      history.pushState({ team: teamName }, "", href);
      filterByTeam(teamName);

      // Scroll to top to see results
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  });
});

/* Mobile Menu Toggle */
document.addEventListener("DOMContentLoaded", () => {
  const hamburger = document.getElementById("hamburger-menu");
  const navLinks = document.getElementById("nav-links");

  if (hamburger && navLinks) {
    hamburger.addEventListener("click", (e) => {
      e.stopPropagation();
      hamburger.classList.toggle("active");
      navLinks.classList.toggle("active");
    });

    // Close menu when clicking outside
    document.addEventListener("click", (e) => {
      if (
        navLinks.classList.contains("active") && !navLinks.contains(e.target)
      ) {
        hamburger.classList.remove("active");
        navLinks.classList.remove("active");
      }
    });

    // Close menu when clicking a link
    navLinks.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        hamburger.classList.remove("active");
        navLinks.classList.remove("active");
      });
    });
  }
});
