var BLUE_ICON = 'http://www.google.com/intl/en_us/mapfiles/ms/micons/blue-dot.png';
var RED_ICON = 'http://www.google.com/intl/en_us/mapfiles/ms/micons/red-dot.png';
var GREEN_ICON = 'http://www.google.com/intl/en_us/mapfiles/ms/micons/green-dot.png';
var TARGET_LOCATION = [59.9135469, 10.7467214];
var BASEIMGURL = 'http://hybel.no';

log4javascript.setEnabled(true);
//log4javascript.setEnabled(false);

function mapImgUrl(house) {
    //return BASEIMGURL + house.image;
    return house.image;
}

function addHover(house, row, marker) {
   log.debug('Add hover', row.attr('id'), marker.getTitle());
   row.find('td').addClass('hover');
   marker.setAnimation(google.maps.Animation.BOUNCE);
   marker.setIcon(GREEN_ICON);
   $("#apt_img").attr('src', mapImgUrl(house));
}

function removeHover(house, row, marker) {
   log.debug('Remove hover', row.attr('id'), marker.getTitle());
   row.find('td').removeClass('hover');
   marker.setAnimation(null);
   marker.setIcon(BLUE_ICON);
}

function initialize() {
    var latlng = new google.maps.LatLng(TARGET_LOCATION[0], TARGET_LOCATION[1]);
    var myOptions = {
      zoom: 14,
      center: latlng,
      mapTypeId: google.maps.MapTypeId.HYBRID
    };
    var map = new google.maps.Map(document.getElementById("map_canvas"),
        myOptions);

    var officeMarker = new google.maps.Marker({
        position: latlng, 
        map: map,
        title: "Office"
        });

    var hideAll = function() {
        $("#apartment").hide();
        $("#apartment_list").hide();
    }
    var showApartment = function() {
        hideAll();
        $("#apartment").show();
    };
    var listings = getListings();
    var bindHouseMarker = function(marker, row, house) {
        google.maps.event.addListener(marker, 'mouseover', function() {
                addHover(house, row, marker);
            });
        google.maps.event.addListener(marker, 'mouseout', function() {
                removeHover(house, row, marker);
            });
        google.maps.event.addListener(marker, 'click', function() {
                $("#apartment").attr('src', house.href);
                showApartment();
            });
    };
    var updateVisible = function() {
        // filters the list of apartments by viewport bounds
        // TODO: optimize with sorted lists, binary search and merge
        for (var i in listings) {
            var house = listings[i];
            var bounds = map.getBounds();
            if (bounds == undefined) return;
            $('#' + house.id).toggle(bounds.contains(house.marker.getPosition()));
        }
    };
 	$.storage = new $.store();
    for (var i in listings) {
        house = listings[i];
        if (house.latlng == undefined) {
            latlng = undefined;
        } else {
            latlng = new google.maps.LatLng(house.latlng.lat, house.latlng.lng);
        }
        title = house.listing_text;
        var marker = new google.maps.Marker({
            icon: BLUE_ICON, 
            position: latlng, 
            map: map,
            title: title
            });
        house.id = 'house' + i;
        house.marker = marker;
        if (house.duration == undefined) {
            duration = '';
            duration_value = ''; // '' works for sorting, replace with ~double.inf?
        } else {
            duration = house.duration.text;
            duration_value = house.duration.value;
        }
        var score = 15*60*6000 / (duration_value * house.price);
        var house_store = $.storage.get(house.href);
        if (house_store == undefined) {
            house_store = {};
            note = "";
        } else {
            note = house_store['usernote'];
        }
        $("#apartment_list").append('<tr class="hover_highlight" id="' + house.id + '">' + 
                '<td class="apt_img"><img style="float: left; max-height: 4em; max-width: 60px;" id="thumb' + i + '" src="' + mapImgUrl(house) + '"></td>' +
                '<td class="apt_created">' + house.created + '"</td>' +
                '<td class="apt_title"><a target="_blank" class="goto_apartment" href="' + house.href + '">' + house.listing_text + '</a>' +
                '<input id="note' + i + '" value="' + note + '"></input>' +
                '</td>' + 
                '<td class="apt_price">' + house.price + '</td>' +
                '<td class="apt_duration">' + duration + '</td>' +
                '<td class="apt_score">' + score.toFixed(2) + '</td>' +
                + '</tr>');
        
//        $("#thumb" + i).css({
//            top: imgtop + 'px',
//            'z-index': i
//            });

        $("#note" + i).change(function(house, house_store) { 
                return function() {
                    house_store['usernote'] = $(this).val();
                    $.storage.set(house.href, house_store);
                }
                }(house, house_store));
        var trow = $('#' + house.id);
        trow.data('index', i);
        trow.find('.apt_title').data('sortvalue', house.listing_text);
        trow.find('.apt_price').data('sortvalue', house.price);
        trow.find('.apt_duration').data('sortvalue', duration_value);
        trow.find('.apt_score').data('sortvalue', score);
        bindHouseMarker(marker, trow, house);
    }
    var sortTextExtraction = function(node) {  
        return $(node).data('sortvalue');
    }; 
    $("#apartment_list").tablesorter(
        {sortList: [[5,1], [4,0]],
         textExtraction: sortTextExtraction});
    //$("#apartment_list").tableHover();
    //$(".goto_apartment").click(function() {});
    $("#apartment_list td").hover(
        function() {
            var tr = $($(this).closest('tr')[0]);
            var house = listings[tr.data('index')];
            addHover(house, tr, house.marker);
        },
        function() {
            var tr = $($(this).closest('tr')[0]);
            var house = listings[tr.data('index')];
            removeHover(house, tr, house.marker);
        }
    );
    updateVisible();
    google.maps.event.addListener(map, 'bounds_changed', updateVisible);
    $("#apartment").hide();
    $("#apartment_link").click(showApartment);
    $("#apartment_list_link").click(function() {
            hideAll();
            $("#apartment_list").show();
            });
}
