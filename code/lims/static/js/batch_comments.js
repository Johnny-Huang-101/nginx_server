$(function() {
    $('#comment_reference').on('change', function() {

        console.log('TEST');

        let selectedValue = $('#comment_reference option:selected').text();
        console.log('VALUE', selectedValue);

        if (selectedValue === 'Other') {
            $('#comment_text').css('display', 'block');
        } else {
            $('#comment_text').css('display', 'none')
        }
    });
});
