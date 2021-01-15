(function(){ // scoping

    var $ontologiesFilter = $('#ontologies-filter');


    $ontologiesFilter.autocomplete({
	minLength: 1
	, delay: 300
	, source: function (request, response) {
	    $.post("/ui/ontologies_suggestions",
		   data={'term': request.term }, // no limit here. Limit in python.
		   response);
	}
	// , focus: function() {
        //     // prevent value inserted on focus
        //     return false;
	// }
	, select: function( event, ui ) {
	    // console.log(ui);
            // $start.val(ui.item.start);
            // $end.val(ui.item.end);
            // $query.val(ui.item.name);
            // this.value = ui.item.name;
            console.log("you clicked ;)");
            console.log(ui.item.meaning);
            console.log(ui.item.ontology);
            return false;
	}

    });

    $ontologiesFilter.autocomplete("enable");
    $ontologiesFilter.attr('autocomplete','off');

})();
