
// ----------------------------------------------
// Join target-selection to result-selection
// ----------------------------------------------

var targetInstance = $("#target-instance");

// define result-option-complex html chunks
function updateOptions(selectedTarget) {
    var dataTarget = selectedTarget.attr("data-target");

    // change result-option-complex 
    var optionsWrapperAll = $(".options-wrapper");
    optionsWrapperAll.removeClass("active");

    var optionsWrapperIndividual = $(".options-wrapper#individual-options");
    var optionsWrapperSample = $(".options-wrapper#sample-options");
    var optionsWrapperVariant = $(".options-wrapper#variant-options");

    if (dataTarget == "individual") {optionsWrapperIndividual.addClass("active")} 
    else if (dataTarget == "sample") {optionsWrapperSample.addClass("active")} 
    else if (dataTarget == "variant") {optionsWrapperVariant.addClass("active")};

    // set targetInstance value
    targetInstance.val(dataTarget);
};

// set at the beginning
$("#result-option-all").attr("value", $(".target-icon.active").attr("data-target"));
updateOptions($(".target-icon.active"));

// set when user clicks
$("#target-selection").on("click",".target-icon", function(){
    var dataTarget = $(this).attr("data-target");

    // deselect all and select this
    $(".target-icon").removeClass("active");
    $(this).addClass("active");

    // set result-selection-all as default and set its target
    $("#result-option-all").attr("value", dataTarget);
    $("#result-option-all").prop("checked", true);
    $(".result-selection").removeClass("active");
    $("#result-selection-all").addClass("active");

    // call function to update result-selection-complex options
    updateOptions($(this));

    // reset targetId and resultOptions
    $("#targetId").val("");
    $("#result-selection-complex .result-option").prop("checked", false);
});


// ----------------------------------------------
// search all or complex
// ----------------------------------------------
$(".result-selection").on("click", function(){
    $(".result-selection").removeClass("active");
    $(this).addClass("active");

    if ($(this).is("#result-selection-complex")) {
        $("#result-selection-all .result-option").prop("checked", false);
        $("#result-selection-complex input").attr("required", true);

    } else if ($(this).is("#result-selection-all")) {
        $("#result-selection-complex .result-option").prop("checked", false);
        $("#result-selection-all .result-option").prop("checked", true);
        $("#result-selection-complex input").val("");
        $("#result-selection-complex input").attr("required", false);
    };
});

// ----------------------------------------------
// Variant filter
// ----------------------------------------------
var variantButton = $(".variant-button");
var variantOption = $(".variant-option");
var variantBasic = $("#variant-basic");
var variantAdvanced = $("#variant-advanced");
var variantInput = $("#variant-option");

variantButton.on("click", function(){
    variantButton.removeClass("active");
    variantOption.removeClass("active");
    var me = $(this);
    me.addClass("active");

    var id = me.attr("id");
    if ( id == "variant-basic-button") {
        variantBasic.addClass("active");
        variantInput.attr("value", "basic");
    } else {
        variantAdvanced.addClass("active");
        variantInput.attr("value", "advanced");
    };
});

// variant advanced position exact/range
var variantPosButton = $("#variant-pos-selection input");
var variantPosOption = $(".variant-pos-option");
var variantPosExact = $("#variant-pos-exact");
var variantPosRange = $("#variant-pos-range");

variantPosButton.on("click", function(){
    variantPosOption.removeClass("active");
    var variantPosValue = $(this).attr("value");
    if ( variantPosValue == "variant-pos-exact") {
        variantPosExact.addClass("active");
    } else {
        variantPosRange.addClass("active");
    };
});



// ----------------------------------------------
// Extra info
// ----------------------------------------------

var mainTable = $("#main-result");
var extraInfo = $("#extra-info");


mainTable.on("click", "td.extra-info-trigger", function(){
    // update content
    var me = $(this);
    var extraInfoHTML = me.siblings("td.hidden").html();
    extraInfo.html(extraInfoHTML);
    // for closing
    extraInfo.on("click", "i.close-button", function(){
        extraInfo.addClass("hidden");
        me.parent().removeClass("active");
    });
    // make side panel visible
    extraInfo.removeClass("hidden");
    // highlight row
    mainTable.find("tr").removeClass("active");
    me.parent().addClass("active");
});



// ----------------------------------------------
// Multiselect dropdown
// ----------------------------------------------

$(document).ready(function() {
    $('#example-getting-started').multiselect();
});