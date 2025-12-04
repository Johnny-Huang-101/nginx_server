
// Highlight the selected text
$('#highlight').on('click', function () {
    if (document.getSelection) {
        selectedText = document.getSelection();
    }

    selectedText = selectedText.toString();
    if (selectedText) {
        var taggedText = "<mark>"+selectedText+"</mark>"
        var highlightedText = $('#narrative').val().replaceAll(selectedText, taggedText);

        $('#narrative').val(highlightedText);
        $('#narrative-text').html(highlightedText);
    }
});


// Remove any red/bolded text which denotes changed text
    $('#remove-changes').on('click', function () {
        var narrativeText = $('#narrative').val().replaceAll("</span>", "")
        console.log(narrativeText);
        const regExp = new RegExp("<span.*?>", "g")
        var matches = narrativeText.matchAll(regExp)
        for (const match of matches) {
          narrativeText = narrativeText.replaceAll(match[0], "")
        }

        $('#narrative').val(narrativeText);
        $('#narrative-text').html(narrativeText);
    });


// unhighlight the selected highlighted text
    $('#unhighlight').on('click', function () {
        if (document.getSelection) {
            selectedText = document.getSelection();
        }

        selectedText = selectedText.toString();
        console.log(selectedText);
        const regExp = new RegExp("(<mark>.*?<\/mark>)", "g")

        var narrativeText =  $('#narrative-text').html();
        var matches = narrativeText.matchAll(regExp)

        for (const match of matches) {
          console.log(match[0])
          var noMark = match[0].match(RegExp('(?<=\<mark>)(.*?)(?=\<\/mark)', 'g'))
          console.log(noMark[0]);
          if (noMark == selectedText) {
            console.log(match[0])
            console.log(selectedText)
            var newText = narrativeText.replaceAll(match[0], selectedText)
            $('#narrative').val(newText);
            $('#narrative-text').html(newText);
          }
        }
    });

// Remove all highlighting
    $('#unhighlight-all').on('click', function () {
        var narrativeText =  $('#narrative-text').html().trim();
        console.log(narrativeText);
        newText = narrativeText.replaceAll("<mark>", "")
        newText = newText.replaceAll("</mark>", "")
        $('#narrative').val(newText);
        $('#narrative-text').html(newText);
    });
