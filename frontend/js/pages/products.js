// js/pages/products.js - Products Page (FIXED FOR YOUR BACKEND)


const ProductsPage = {
    currentPage: 1,
    limit: 50,
    totalProducts: 0,
    filters: {},
    allProducts: [],
    categories: {},


    async render() {
        const content = document.getElementById('main-content');


        content.innerHTML = `
            <div class="container">
                <div class="flex justify-between items-center mb-6">
                    <h1><i class="fas fa-barcode"></i> Products Catalog</h1>
                    <div class="flex gap-2">
                        <button class="btn btn-secondary" onclick="ProductsPage.exportToCSV()">
                            <i class="fas fa-download"></i> Export CSV
                        </button>
                        <button class="btn btn-ghost" onclick="ProductsPage.refresh()">
                            <i class="fas fa-sync"></i> Refresh
                        </button>
                    </div>
                </div>


                <!-- Search & Filters Card -->
                <div class="card mb-6">
                    <div class="card-body">
                        <div class="grid grid-cols-4 gap-4">
                            <div class="input-group" style="grid-column: span 2;">
                                <div class="input-group-prepend">
                                    <i class="fas fa-search"></i>
                                </div>
                                <input 
                                    type="text" 
                                    class="form-input" 
                                    id="search-input" 
                                    placeholder="Search by name or UPC..."
                                >
                            </div>
                            <select class="form-select" id="category-filter" onchange="ProductsPage.onCategoryChange()">
                                <option value="">All Categories</option>
                            </select>
                            <select class="form-select" id="subcategory-filter">
                                <option value="">All Subcategories</option>
                            </select>
                        </div>
                        <div class="flex gap-2" style="margin-top: 1rem;">
                            <button class="btn btn-primary" onclick="ProductsPage.search()">
                                <i class="fas fa-search"></i> Search
                            </button>
                            <button class="btn btn-ghost" onclick="ProductsPage.clearFilters()">
                                <i class="fas fa-times"></i> Clear Filters
                            </button>
                        </div>
                    </div>
                </div>


                <!-- Products Table Card -->
                <div class="card">
                    <div class="card-header">
                        <h3 class="card-title">
                            <i class="fas fa-list"></i> Product List
                        </h3>
                        <div id="product-count" style="color: var(--text-secondary); font-size: 0.875rem;">
                            Loading...
                        </div>
                    </div>
                    <div class="card-body">
                        <div id="products-container">
                            <div class="loader-container">
                                <div class="loader"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;


        await this.loadCategories();
        await this.loadProducts();
        this.attachEvents();
    },


    async loadCategories() {
        try {
            const response = await API.products.getCategories();
            console.log('Categories API response:', response);
            
            // ✅ THIS IS THE FIX - RIGHT HERE
            const categoriesData = response.categories || response;
            this.categories = categoriesData;

            const categorySelect = document.getElementById('category-filter');
            categorySelect.innerHTML = '<option value="">All Categories</option>' +
                Object.keys(categoriesData).map(cat => 
                    `<option value="${cat}">${Utils.capitalize(cat.replace('_', ' '))}</option>`
                ).join('');
                
            console.log('Categories loaded:', Object.keys(categoriesData));
        } catch (error) {
            console.error('Failed to load categories:', error);
            Notification.error('Failed to load categories');
        }
    },


    onCategoryChange() {
        const category = document.getElementById('category-filter').value;
        const subcategorySelect = document.getElementById('subcategory-filter');

        if (!category || !this.categories || !this.categories[category]) {
            subcategorySelect.innerHTML = '<option value="">All Subcategories</option>';
            return;
        }


        const subcategories = this.categories[category];
        subcategorySelect.innerHTML = '<option value="">All Subcategories</option>' +
            subcategories.map(sub => 
                `<option value="${sub}">${Utils.capitalize(sub)}</option>`
            ).join('');
    },


    async loadProducts() {
        try {
            console.log('Loading products with filters:', this.filters);

            // FIXED: Backend returns { success, products, total }
            const response = await API.products.list({
                ...this.filters,
                limit: this.limit,
                offset: (this.currentPage - 1) * this.limit
            });

            console.log('Products API response:', response);


            // FIXED: Extract products array from response
            const products = response.products || [];
            this.totalProducts = response.total || products.length;
            this.allProducts = products;


            this.displayProducts(products);
            this.updateProductCount(products.length, this.totalProducts);
        } catch (error) {
            console.error('Failed to load products:', error);
            Notification.error('Failed to load products');

            document.getElementById('products-container').innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>Error Loading Products</h3>
                    <p>${error.message || 'Please try again later'}</p>
                </div>
            `;
        }
    },


    displayProducts(products) {
        const container = document.getElementById('products-container');


        if (products.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-box-open"></i>
                    <h3>No Products Found</h3>
                    <p>Try adjusting your search or filters</p>
                </div>
            `;
            return;
        }


        const tableHtml = `
            <div class="table-container">
                <table class="table">
                    <thead>
                        <tr>
                            <th style="width: 150px;">UPC</th>
                            <th>Product Name</th>
                            <th style="width: 150px;">Category</th>
                            <th style="width: 150px;">Subcategory</th>
                            <th style="width: 120px; text-align: center;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${products.map(product => `
                            <tr>
                                <td>
                                    <code style="font-size: 0.875rem; background: var(--bg-secondary); padding: 0.25rem 0.5rem; border-radius: 4px;">
                                        ${product.upc}
                                    </code>
                                </td>
                                <td>
                                    <strong>${Utils.escapeHtml(product.name)}</strong>
                                </td>
                                <td>
                                    <span class="badge badge-secondary">
                                        ${Utils.capitalize((product.main_category || 'N/A').replace('_', ' '))}
                                    </span>
                                </td>
                                <td>
                                    <span class="badge badge-ghost">
                                        ${Utils.capitalize(product.subcategory || 'N/A')}
                                    </span>
                                </td>
                                <td style="text-align: center;">
                                    <button 
                                        class="btn btn-sm btn-ghost" 
                                        onclick="ProductsPage.copyUPC('${product.upc}')"
                                        title="Copy UPC to clipboard"
                                    >
                                        <i class="fas fa-copy"></i>
                                    </button>
                                    <button 
                                        class="btn btn-sm btn-ghost" 
                                        onclick="ProductsPage.viewDetails('${product.upc}')"
                                        title="View details"
                                    >
                                        <i class="fas fa-eye"></i>
                                    </button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;


        container.innerHTML = tableHtml;
    },


    updateProductCount(displayCount, total) {
        const countDiv = document.getElementById('product-count');
        const searchInput = document.getElementById('search-input');
        const query = searchInput ? searchInput.value.trim() : '';

        if (query) {
            countDiv.textContent = `Found ${displayCount} of ${total} products`;
        } else {
            countDiv.textContent = `Showing ${displayCount} of ${total} products`;
        }
    },


    attachEvents() {
        const searchInput = document.getElementById('search-input');
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.search();
            }
        });


        // Real-time search (debounced)
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            const value = e.target.value.trim();

            if (value.length >= 3) {
                searchTimeout = setTimeout(() => this.search(), 500);
            } else if (value.length === 0) {
                this.clearFilters();
            }
        });
    },


    async search() {
        const query = document.getElementById('search-input').value.trim();
        const category = document.getElementById('category-filter').value;
        const subcategory = document.getElementById('subcategory-filter').value;


        this.filters = {};
        if (category) this.filters.main_category = category;
        if (subcategory) this.filters.subcategory = subcategory;


        if (query) {
            try {
                // FIXED: Backend returns { success, products, total }
                const response = await API.products.search(query, this.filters);
                console.log('Search response:', response);

                const products = response.products || [];
                const total = response.total || products.length;

                this.allProducts = products;
                this.totalProducts = total;
                this.displayProducts(products);
                this.updateProductCount(products.length, total);
            } catch (error) {
                console.error('Search failed:', error);
                Notification.error('Search failed');
            }
        } else {
            await this.loadProducts();
        }
    },


    async clearFilters() {
        document.getElementById('search-input').value = '';
        document.getElementById('category-filter').value = '';
        document.getElementById('subcategory-filter').value = '';
        this.filters = {};
        this.currentPage = 1;
        await this.loadProducts();
        Notification.info('Filters cleared');
    },


    async refresh() {
        Notification.info('Refreshing products...');
        await this.loadProducts();
        Notification.success('Products refreshed');
    },


    async copyUPC(upc) {
        try {
            await navigator.clipboard.writeText(upc);
            Notification.success(`UPC ${upc} copied to clipboard`);
        } catch (error) {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = upc;
            textArea.style.position = 'fixed';
            textArea.style.left = '-999999px';
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                Notification.success(`UPC ${upc} copied to clipboard`);
            } catch (err) {
                Notification.error('Failed to copy UPC');
            }
            document.body.removeChild(textArea);
        }
    },


    viewDetails(upc) {
        const product = this.allProducts.find(p => p.upc === upc);
        if (!product) {
            Notification.error('Product not found');
            return;
        }


        Modal.create({
            title: `<i class="fas fa-barcode"></i> Product Details`,
            content: `
                <div style="padding: 1rem;">
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.75rem; font-weight: 600; width: 40%;">UPC Code:</td>
                            <td style="padding: 0.75rem;">
                                <code style="background: var(--bg-secondary); padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 1rem;">
                                    ${product.upc}
                                </code>
                            </td>
                        </tr>
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.75rem; font-weight: 600;">Product Name:</td>
                            <td style="padding: 0.75rem;">${Utils.escapeHtml(product.name)}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.75rem; font-weight: 600;">Main Category:</td>
                            <td style="padding: 0.75rem;">
                                <span class="badge badge-secondary">
                                    ${Utils.capitalize((product.main_category || 'N/A').replace('_', ' '))}
                                </span>
                            </td>
                        </tr>
                        <tr>
                            <td style="padding: 0.75rem; font-weight: 600;">Subcategory:</td>
                            <td style="padding: 0.75rem;">
                                <span class="badge badge-ghost">
                                    ${Utils.capitalize(product.subcategory || 'N/A')}
                                </span>
                            </td>
                        </tr>
                    </table>
                </div>
            `,
            actions: [
                {
                    label: 'Copy UPC',
                    variant: 'secondary',
                    action: (modal) => {
                        this.copyUPC(product.upc);
                    }
                },
                {
                    label: 'Close',
                    variant: 'primary',
                    action: (modal) => modal.close()
                }
            ]
        });
    },


    exportToCSV() {
        if (this.allProducts.length === 0) {
            Notification.error('No products to export');
            return;
        }


        try {
            // CSV Header
            const headers = ['UPC', 'Product Name', 'Main Category', 'Subcategory'];
            const csvRows = [headers.join(',')];


            // CSV Data
            this.allProducts.forEach(product => {
                const row = [
                    `"${product.upc}"`,
                    `"${product.name.replace(/"/g, '""')}"`,
                    `"${(product.main_category || 'N/A').replace('_', ' ')}"`,
                    `"${product.subcategory || 'N/A'}"`
                ];
                csvRows.push(row.join(','));
            });


            // Create Blob and download
            const csvContent = csvRows.join('\n');
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);

            const timestamp = new Date().toISOString().split('T')[0];
            link.setAttribute('href', url);
            link.setAttribute('download', `products_${timestamp}.csv`);
            link.style.visibility = 'hidden';

            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);


            Notification.success(`Exported ${this.allProducts.length} products to CSV`);
        } catch (error) {
            console.error('Export failed:', error);
            Notification.error('Failed to export CSV');
        }
    },


    cleanup() {
        this.currentPage = 1;
        this.filters = {};
        this.allProducts = [];
    }
};
