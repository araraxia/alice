/**
 * Drag Window Functionality
 * Makes elements draggable by their title bars
 */

class DragWindow {
    constructor(containerSelector, titleBarSelector) {
        // Handle both selector strings and DOM elements
        if (typeof containerSelector === 'string') {
            this.container = document.querySelector(containerSelector);
        } else if (containerSelector instanceof HTMLElement) {
            this.container = containerSelector;
        } else {
            console.warn('DragWindow: Invalid container parameter');
            return;
        }

        // Handle title bar selector
        if (typeof titleBarSelector === 'string') {
            this.titleBar = this.container ? this.container.querySelector(titleBarSelector) : null;
        } else if (titleBarSelector instanceof HTMLElement) {
            this.titleBar = titleBarSelector;
        } else {
            console.warn('DragWindow: Invalid title bar parameter');
            return;
        }
        
        if (!this.container || !this.titleBar) {
            console.warn('DragWindow: Container or title bar not found');
            return;
        }
        
        this.isDragging = false;
        this.startX = 0;
        this.startY = 0;
        this.offsetX = 0;
        this.offsetY = 0;
        
        this.init();
    }
    
    init() {
        // Set initial position styles
        this.container.style.position = 'absolute';
        this.container.style.cursor = 'default';
        
        // Make title bar indicate it's draggable
        this.titleBar.style.cursor = 'move';
        this.titleBar.style.userSelect = 'none';
        
        // Add event listeners
        this.titleBar.addEventListener('mousedown', this.handleMouseDown.bind(this));
        document.addEventListener('mousemove', this.handleMouseMove.bind(this));
        document.addEventListener('mouseup', this.handleMouseUp.bind(this));
        
        // Prevent text selection while dragging
        this.titleBar.addEventListener('selectstart', (e) => e.preventDefault());
    }
    
    handleMouseDown(e) {
        this.isDragging = true;
        
        // Get the current position of the container
        const rect = this.container.getBoundingClientRect();
        
        // Calculate offset from mouse to top-left corner of container
        this.offsetX = e.clientX - rect.left;
        this.offsetY = e.clientY - rect.top;
        
        // Add dragging class for visual feedback
        this.container.classList.add('dragging');
        this.titleBar.style.cursor = 'grabbing';
        
        // Prevent default to avoid text selection
        e.preventDefault();
    }
    
    handleMouseMove(e) {
        if (!this.isDragging) return;
        
        // Calculate new position
        const newX = e.clientX - this.offsetX;
        const newY = e.clientY - this.offsetY;
        
        // Get viewport dimensions
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const containerRect = this.container.getBoundingClientRect();
        
        // Constrain to viewport bounds
        const constrainedX = Math.max(0, Math.min(newX, viewportWidth - containerRect.width));
        const constrainedY = Math.max(0, Math.min(newY, viewportHeight - containerRect.height));
        
        // Apply new position
        this.container.style.left = constrainedX + 'px';
        this.container.style.top = constrainedY + 'px';
    }
    
    handleMouseUp(e) {
        if (!this.isDragging) return;
        
        this.isDragging = false;
        
        // Remove dragging class
        this.container.classList.remove('dragging');
        this.titleBar.style.cursor = 'move';
    }
    
    // Center the window in the viewport
    center() {
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const containerRect = this.container.getBoundingClientRect();
        
        const centerX = (viewportWidth - containerRect.width) / 2;
        const centerY = (viewportHeight - containerRect.height) / 2;
        
        this.container.style.left = centerX + 'px';
        this.container.style.top = centerY + 'px';
    }
}

// Make DragWindow available globally for modular usage
window.DragWindow = DragWindow;
