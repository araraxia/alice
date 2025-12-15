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
        
        // Clear any conflicting CSS positioning when drag starts
        const computedStyle = window.getComputedStyle(this.container);
        if (computedStyle.position === 'absolute') {
            // If already positioned, preserve current position
            if (computedStyle.right !== 'auto' && computedStyle.left === 'auto') {
                // Convert right positioning to left positioning
                const rightValue = parseInt(computedStyle.right) || 0;
                const leftValue = window.innerWidth - this.container.offsetWidth - rightValue;
                this.container.style.left = leftValue + 'px';
                this.container.style.right = 'auto';
            }
            if (computedStyle.bottom !== 'auto' && computedStyle.top === 'auto') {
                // Convert bottom positioning to top positioning
                const bottomValue = parseInt(computedStyle.bottom) || 0;
                const topValue = window.innerHeight - this.container.offsetHeight - bottomValue;
                this.container.style.top = topValue + 'px';
                this.container.style.bottom = 'auto';
            }
        }
        
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
        
        // Get the current computed position (not bounding rect)
        const computedStyle = window.getComputedStyle(this.container);
        const currentLeft = parseInt(computedStyle.left) || 0;
        const currentTop = parseInt(computedStyle.top) || 0;
        
        // Store the starting mouse position and element position
        this.startX = e.clientX;
        this.startY = e.clientY;
        this.startLeft = currentLeft;
        this.startTop = currentTop;
        
        // Add dragging class for visual feedback
        this.container.classList.add('dragging');
        this.titleBar.style.cursor = 'grabbing';
        
        // Prevent default to avoid text selection
        e.preventDefault();
    }
    
    handleMouseMove(e) {
        if (!this.isDragging) return;
        
        // Calculate the distance moved from start position
        const deltaX = e.clientX - this.startX;
        const deltaY = e.clientY - this.startY;
        
        // Calculate new position (1:1 ratio with mouse movement)
        const newX = this.startLeft + deltaX;
        const newY = this.startTop + deltaY;
        
        // Get viewport dimensions and container dimensions
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const containerWidth = this.container.offsetWidth;
        const containerHeight = this.container.offsetHeight;
        
        // Constrain to viewport bounds (allow full left side)
        const constrainedX = Math.max(0, Math.min(newX, viewportWidth - containerWidth));
        const constrainedY = Math.max(0, Math.min(newY, viewportHeight - containerHeight));
        
        // Apply new position
        this.container.style.left = constrainedX + 'px';
        this.container.style.top = constrainedY + 'px';
        
        // Clear any conflicting CSS positioning
        this.container.style.right = 'auto';
        this.container.style.bottom = 'auto';
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
        
        console.log(`Viewport: ${viewportWidth}x${viewportHeight}`);
        console.log(`Container: ${containerRect.width}x${containerRect.height}`);
        
        // Check if the container height is unrealistic (likely not fully rendered)
        if (containerRect.height > viewportHeight * 1.5) {
            console.warn(`Container height (${containerRect.height}px) seems too large. Waiting for proper rendering...`);
            
            // Try again after a short delay
            setTimeout(() => {
                this.center();
            }, 50);
            return;
        }
        
        const centerX = Math.max(0, (viewportWidth - containerRect.width) / 2);
        const centerY = Math.max(0, (viewportHeight - containerRect.height) / 2);
        
        console.log(`Centering window to (${centerX}, ${centerY})`);
        
        this.container.style.left = centerX + 'px';
        this.container.style.top = centerY + 'px';
    }
}

// Make DragWindow available globally for modular usage
window.DragWindow = DragWindow;
