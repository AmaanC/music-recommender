(function() {
    var API_URL = '/api/v1.0/';
    var bands = [];
    var bandSelect = document.getElementById('bandSelect');
    var userSelect = document.getElementById('userSelect');
    var bandList = document.getElementById('bandList');
    var userList = document.getElementById('userList');
    var userInput = document.getElementById('userInput');

    var getSimilarBtn = document.getElementById('getSimilarBtn');
    var getUserForm = document.getElementById('getUserForm');

    var init = function() {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', API_URL + 'band/');
        xhr.addEventListener('load', function() {
            bands = JSON.parse(this.responseText).bands;
            console.log('Received response');

            bands.forEach(function(band) {
                var optionElem1 = document.createElement('option');
                var optionElem2 = document.createElement('option');
                optionElem1.textContent = optionElem2.textContent = band;

                bandSelect.appendChild(optionElem1);
                userSelect.appendChild(optionElem2);    
            });
            $('.selectpicker').selectpicker('refresh');
        });
        xhr.send();

        console.log('Request sent');
    };

    var clearChildren = function(nodeElem) {
        while (nodeElem.children.length > 0) {
            nodeElem.removeChild(nodeElem.children[0]);
        }
    };

    var getSimilar = function() {
        var band = bandSelect.selectedOptions[0].textContent;
        var xhr = new XMLHttpRequest();
        xhr.open('GET', API_URL + 'band/' + band);
        xhr.addEventListener('load', function() {
            var respObj = JSON.parse(this.responseText);
            if (respObj.error) {
                console.error(respObj.error);
                return;
            }
            var similarBands = respObj.similar;
            console.log('Received similar bands');
            clearChildren(bandList);
            similarBands.slice(0, 5).forEach(function(recBand) {
                var listItem = document.createElement('li');
                listItem.textContent = recBand;
                listItem.className = 'list-group-item';

                bandList.appendChild(listItem);
            });
            $('.selectpicker').selectpicker('refresh');
        });
        xhr.send();
    };

    var getUserRecs = function(e) {
        var id = parseInt(userInput.value, 10);
        var xhr = new XMLHttpRequest();
        xhr.open('GET', API_URL + 'user/' + id);
        xhr.addEventListener('load', function() {
            var respObj = JSON.parse(this.responseText);
            if (respObj.error) {
                console.error(respObj.error);
                return;
            }
            var similarBands = respObj.recommendations;
            console.log('Received similar bands');
            clearChildren(userList);
            similarBands.slice(0, 5).forEach(function(recBand) {
                var listItem = document.createElement('li');
                listItem.textContent = recBand;
                listItem.className = 'list-group-item';

                userList.appendChild(listItem);
            });
            $('.selectpicker').selectpicker('refresh');
        });
        xhr.send();

        e.preventDefault();
        return false;
    };

    window.addEventListener('load', init);
    getSimilarBtn.addEventListener('click', getSimilar);
    getUserForm.addEventListener('submit', getUserRecs);
})();