document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const searchForm = document.querySelector('.search-form');
    let autocompleteWrapper;

    searchInput.addEventListener('input', async (e) => {
        const query = e.target.value;

        if (autocompleteWrapper) {
            autocompleteWrapper.remove();
        }

        if (query.length < 2) {
            return;
        }

        const response = await fetch(`/autocomplete?query=${query}`);
        const data = await response.json();

        if (data.titles.length === 0 && data.topics.length === 0) {
            return;
        }

        autocompleteWrapper = document.createElement('div');
        autocompleteWrapper.className = 'autocomplete-wrapper';
        searchForm.appendChild(autocompleteWrapper);

        const fullTextSearch = document.createElement('a');
        fullTextSearch.href = `/?search=${query}`;
        fullTextSearch.innerHTML = `Perform full text search for '<strong>${query}</strong>'`;
        fullTextSearch.className = 'autocomplete-item';
        autocompleteWrapper.appendChild(fullTextSearch);

        if (data.titles.length > 0) {
            const titleHeader = document.createElement('div');
            titleHeader.className = 'autocomplete-header';
            titleHeader.textContent = 'Titles';
            autocompleteWrapper.appendChild(titleHeader);

            data.titles.forEach(kata => {
                const item = document.createElement('a');
                item.href = `/kata/${kata.id}`;
                item.textContent = kata.title;
                item.className = 'autocomplete-item';
                autocompleteWrapper.appendChild(item);
            });
        }

        if (data.topics.length > 0) {
            const topicHeader = document.createElement('div');
            topicHeader.className = 'autocomplete-header';
            topicHeader.textContent = 'Topics';
            autocompleteWrapper.appendChild(topicHeader);

            data.topics.forEach(topic => {
                const item = document.createElement('a');
                item.href = `/?topic=${topic}`;
                item.textContent = topic;
                item.className = 'autocomplete-item';
                autocompleteWrapper.appendChild(item);
            });
        }
    });

    document.addEventListener('click', (e) => {
        if (autocompleteWrapper && !searchForm.contains(e.target)) {
            autocompleteWrapper.remove();
        }
    });

    let activeIndex = -1;

    searchInput.addEventListener('keydown', (e) => {
        if (!autocompleteWrapper) return;

        const items = autocompleteWrapper.querySelectorAll('.autocomplete-item');
        if (items.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            activeIndex++;
            if (activeIndex >= items.length) activeIndex = 0;
            updateActive(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            activeIndex--;
            if (activeIndex < 0) activeIndex = items.length - 1;
            updateActive(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (activeIndex > -1) {
                items[activeIndex].click();
            }
        }
    });

    function updateActive(items) {
        items.forEach((item, index) => {
            if (index === activeIndex) {
                item.classList.add('active');
            } else {
                item.classList.remove('active');
            }
        });
    }
});