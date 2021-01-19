(function(){ // scoping

    var $ontologiesFilter = $('#ontologies-filter');
    var $ontologiesFilterHidden = $("#filters-hidden");
    var $ontologiesTags = $("#filters-tags");
    var selectedOntologies = [];
    if ($ontologiesFilterHidden.val()) {
        var selectedOntologies = $ontologiesFilterHidden.val().split(",");
    };

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
            // activate div
            if (!$ontologiesTags.hasClass("active")) {
                $ontologiesTags.addClass("active");
            };
            if (selectedOntologies.indexOf(ui.item.label) == -1) {
                // create tag
                $ontologiesTags.append("<span data-ontology='"+ui.item.label+"' >"+ui.item.label+"<i class='fas fa-times'></i></span>")
                // add to list
                selectedOntologies.push(ui.item.label);
                // update hidden input
                $ontologiesFilterHidden.val(selectedOntologies.join());
            };
            // clean input
            $ontologiesFilter.val("");
            return false;
	}

    });

    $ontologiesFilter.autocomplete("enable");
    $ontologiesFilter.attr('autocomplete','off');


    // remove tags
    $ontologiesTags.on("click", "i", function(){
        // update list
        var me = $(this);
        var ontologyTerm = me.parent().attr("data-ontology");
        selectedOntologies = jQuery.grep(selectedOntologies, function(value) {
            return value != ontologyTerm;
        });
        // remove tag
        me.parent().remove();
        // update hidden input
        $ontologiesFilterHidden.val(selectedOntologies.join());
        // removing div if no tags
        if (selectedOntologies.length === 0) {
            $ontologiesTags.removeClass("active");
        }
    });

})();
