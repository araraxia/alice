/**
 * Showcase Window - Project Documentation System
 * Handles navigation, content loading, and rendering
 * Markdown is rendered server-side and delivered as HTML
 */

// Only define ShowcaseManager if it doesn't exist
if (typeof ShowcaseManager === 'undefined') {
  window.ShowcaseManager = class ShowcaseManager {
  constructor() {
    this.currentTopic = null;
    this.navigation = null;
    this.navElement = document.getElementById("showcase-nav");
    this.articleElement = document.getElementById("showcase-article");
    this.eventListeners = []; // Track event listeners for cleanup

    this.init();
  }

  async init() {
    try {
      // Load navigation structure
      await this.loadNavigation();

      // Render navigation
      this.renderNavigation();

      // Load default topic if specified in URL hash, otherwise load welcome
      const hash = window.location.hash.slice(1);
      const topicToLoad = hash || 'welcome';
      this.loadTopic(topicToLoad);
    } catch (error) {
      console.error("Failed to initialize showcase:", error);
      this.showError("Failed to load showcase content");
    }

    // Center and position window AFTER content is rendered to prevent jumping
    // Use setTimeout to ensure DOM has finished updating
    setTimeout(() => {
      window.windowManager.centerWindow("showcase-window");
      window.windowManager.bringToFront("showcase-window");
    }, 0);
    
    // Set up close button handler
    const closeBtn = document.getElementById("close-showcase-button");
    if (closeBtn) {
      const closeHandler = () => {
        console.log('[showcase.js] Cleaning up showcaseManager instance on close');
        this.destroy();
      };
      closeBtn.addEventListener("click", closeHandler);
      this.eventListeners.push({ element: closeBtn, event: "click", handler: closeHandler });
    } else {
      console.warn("Close button with ID 'close-showcase-button' not found");
    }
  }

  async loadNavigation() {
    try {
      const response = await fetch("/showcase/navigation");
      if (!response.ok) {
        throw new Error("Failed to load navigation");
      }
      this.navigation = await response.json();
      console.log("[showcase.js] Navigation content loaded");
    } catch (error) {
      console.error("Error loading navigation:", error);
      throw error;
    }
  }

  renderNavigation() {
    if (!this.navigation || !this.navigation.categories) {
      this.navElement.innerHTML =
        '<p style="padding: 20px; color: #999;">No content available</p>';
      return;
    }

    this.navElement.innerHTML = "";

    this.navigation.categories.forEach((category) => {
      const categoryDiv = document.createElement("div");
      categoryDiv.className = "nav-category";

      // Category header
      const header = document.createElement("div");
      header.className = "category-header";
      header.innerHTML = `
        <span>${category.name}</span>
        <span class="category-toggle">▼</span>
      `;

      // Category items container
      const itemsDiv = document.createElement("div");
      itemsDiv.className = "category-items";

      // Calculate max-height for smooth collapse animation
      const itemHeight = 36; // Approximate height per item
      itemsDiv.style.maxHeight = `${category.items.length * itemHeight}px`;

      // Add items
      category.items.forEach((item) => {
        const itemLink = document.createElement("a");
        itemLink.className = "nav-item";
        itemLink.textContent = item.title;
        itemLink.href = `#${item.id}`;
        itemLink.dataset.topicId = item.id;

        const itemClickHandler = (e) => {
          e.preventDefault();
          this.loadTopic(item.id);
          window.location.hash = item.id;
        };
        itemLink.addEventListener("click", itemClickHandler);
        this.eventListeners.push({ element: itemLink, event: "click", handler: itemClickHandler });

        itemsDiv.appendChild(itemLink);
      });

      // Toggle collapse on header click
      const headerClickHandler = () => {
        header.classList.toggle("collapsed");
        itemsDiv.classList.toggle("collapsed");
      };
      header.addEventListener("click", headerClickHandler);
      this.eventListeners.push({ element: header, event: "click", handler: headerClickHandler });

      categoryDiv.appendChild(header);
      categoryDiv.appendChild(itemsDiv);
      this.navElement.appendChild(categoryDiv);
    });
  }

  async loadTopic(topicId) {
    try {
      this.showLoading();

      const response = await fetch(`/showcase/topic/${topicId}`);
      if (!response.ok) {
        throw new Error("Failed to load topic");
      }

      const data = await response.json();

      if (data.status === "success") {
        this.renderContent(data.content);
        this.updateActiveNav(topicId);
        this.currentTopic = topicId;

        // Update hash if not already set (for default welcome topic)
        if (!window.location.hash && topicId === 'welcome') {
          window.location.hash = topicId;
        }

        // Scroll to top of content
        this.articleElement.scrollTop = 0;
        window.windowManager.centerWindow("showcase-window");
      } else {
        throw new Error(data.message || "Unknown error");
      }
    } catch (error) {
      console.error("Error loading topic:", error);
      this.showError(`Failed to load topic: ${error.message}`);
    }
  }

  renderContent(htmlContent) {
    try {
      // Content is already rendered as HTML by the backend
      this.articleElement.innerHTML = htmlContent;

      // Restore natural window sizing after content loads
      const windowElement = document.getElementById('showcase-window');
      if (windowElement) {
        windowElement.style.width = '';
        windowElement.style.height = '';
      }

      // Add syntax highlighting if available
      if (typeof Prism !== "undefined") {
        Prism.highlightAllUnder(this.articleElement);
      }
    } catch (error) {
      console.error("Error rendering content:", error);
      this.showError("Failed to render content");
    }
  }

  updateActiveNav(topicId) {
    // Remove active class from all items
    const allItems = this.navElement.querySelectorAll(".nav-item");
    allItems.forEach((item) => item.classList.remove("active"));

    // Add active class to selected item
    const activeItem = this.navElement.querySelector(
      `[data-topic-id="${topicId}"]`,
    );
    if (activeItem) {
      activeItem.classList.add("active");
    }
  }

  showLoading() {
    // Capture current window dimensions to prevent resizing during load
    const windowElement = document.getElementById('showcase-window');
    if (windowElement) {
      const currentWidth = windowElement.offsetWidth;
      const currentHeight = windowElement.offsetHeight;
      
      // Fix dimensions during loading
      windowElement.style.width = currentWidth + 'px';
      windowElement.style.height = currentHeight + 'px';
    }
    
    this.articleElement.innerHTML = `
      <div class="loading-message">
        <p>Loading content...</p>
      </div>
    `;
  }

  showError(message) {
    // Capture current window dimensions to prevent resizing during error display
    const windowElement = document.getElementById('showcase-window');
    if (windowElement) {
      const currentWidth = windowElement.offsetWidth;
      const currentHeight = windowElement.offsetHeight;
      
      // Fix dimensions during error display
      windowElement.style.width = currentWidth + 'px';
      windowElement.style.height = currentHeight + 'px';
    }
    
    this.articleElement.innerHTML = `
      <div class="error-message">
        <p><strong>Error:</strong> ${this.escapeHtml(message)}</p>
      </div>
    `;
  }

  escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  destroy() {
    console.log('[showcase.js] Destroying ShowcaseManager instance');
    
    // Remove all tracked event listeners
    this.eventListeners.forEach(({ element, event, handler }) => {
      if (element) {
        element.removeEventListener(event, handler);
      }
    });
    this.eventListeners = [];
    
    // Restore natural window sizing if it was fixed
    const windowElement = document.getElementById('showcase-window');
    if (windowElement) {
      windowElement.style.width = '';
      windowElement.style.height = '';
    }
    
    // Clear references
    this.navElement = null;
    this.articleElement = null;
    this.navigation = null;
    this.currentTopic = null;
    
    // Null the global reference
    window.showcaseManager = null;
    
    console.log('[showcase.js] ShowcaseManager destroyed and ready for re-initialization');
  }
};

  console.log('[showcase.js] ShowcaseManager class defined');
} else {
  console.log('[showcase.js] ShowcaseManager class already exists, skipping definition');
}

// Initialize showcase immediately since this script loads after the HTML
// (DOMContentLoaded has already fired when dynamically loaded)
(function initShowcase() {
  console.log("[showcase.js] Initializing showcase...");

  // Check if DOM is ready
  if (document.readyState === "loading") {
    // Still loading, wait for DOMContentLoaded
    document.addEventListener("DOMContentLoaded", createShowcaseManager);
  } else {
    // DOM already loaded, initialize immediately
    createShowcaseManager();
  }

  function createShowcaseManager() {
    // Clean up existing instance if it exists
    if (window.showcaseManager && typeof window.showcaseManager.destroy === 'function') {
      console.log('[showcase.js] Cleaning up existing ShowcaseManager instance');
      window.showcaseManager.destroy();
    }
    
    if (document.getElementById("showcase-nav")) {
      console.log("[showcase.js] Creating ShowcaseManager instance");
      window.showcaseManager = new ShowcaseManager();
    } else {
      console.warn("[showcase.js] showcase-nav element not found");
    }
  }
})();
