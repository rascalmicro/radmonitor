/*
** This code currently calls the database to get CPS twice. Could probably fix.
** Uses JQuery, JQuery-timeago, D3, D3-hexbin plugin, and Flot libraries
** TODO: Can probably clean up/reorganize the code
** TODO: Make sure variables are scoped properly
** TODO: May/may not want to abstract out HexOverlay to make it an object
** TODO: Add routes for each detector, add ability to select data from individual detector
** TODO: Fix tooltip behavior
*/

var map;
var coords = new google.maps.MVCArray;
var path;		//Draws the path
var bounds;		//used to recenter the map
var cps;
var hexOverlay = new google.maps.OverlayView();
var realtime;	//used to stop execution of realTime()
var tdelta = 3*60*1000	//Width of the real time window in milliseconds
var start;
var end;

//On DOM ready
$(document).ready(function() {
	
	var padding = 20;
	$("#display").css("padding-left", padding);
	$("#display").css("width", $(window).width() - $("#controls").width() -padding*2)
	
	start = $('#start').val();
	end = $('#end').val();

	google.maps.event.addDomListener(window, 'load', initialize);
	
	//Graphs
    cpsoptions = {
        series: {shadowSize: 0},
        legend: {show: false},
        xaxis: {mode: "time", timeformat: "%h:%M:%S", show: true}
    };
    
    hdopoptions = {
        series: {shadowSize: 0},
        legend: {show: false},
        xaxis: {mode: "time", timeformat: "%h:%M:%S", show: true},
        yaxis: {min: 0, max: 10.0}
    };
	
	histoptions = {
        series: {shadowSize: 0},
        legend: {show: false},
		grid: {hoverable: true}
    };
    
    cpsplot = $.plot($("#cpsplot"), [[]], cpsoptions);
    hdopplot = $.plot($("#hdopplot"), [[]], hdopoptions);
	histplot = $.plot($("#histplot"), [[]], histoptions);
	
	//PlotHover displays energy
	var previouspoint = null;
	$("#histplot").bind("plothover", function (event, pos, item) {
		    if (item != null) {
                if (previousPoint != item.dataIndex) {
                    previousPoint = item.dataIndex;
                    
                    $("#tooltip").remove();
                    var x = item.datapoint[0].toFixed(2),
						y = item.datapoint[1].toFixed(2);
                    
                    showTooltip(item.pageX, item.pageY,
                                "Energy: " + x + " keV, Counts: " + y);
                }
            }
            else {
                $("#tooltip").remove();
                previousPoint = null;            
            }
	});
	checkStatus();
	
	//Redraw plots on window resize
	$(window).resize(function() {
		$("#display").css("width", $(window).width() - $("#controls").width() -padding*2)
		cpsplot.resize();
		cpsplot.draw();
		cpsplot.setupGrid();
		
		hdopplot.resize();
		hdopplot.draw();
		hdopplot.setupGrid();
		
		histplot.resize();
		histplot.draw();
		histplot.setupGrid();
	});
	
	$(window).unload(function() {
		clearInterval(realtime);
		realtime = null;
	});
});

//GoogleMaps
function initialize() {
	$.getJSON("/recentloc/",{"start": start, "end": end}, function(data) {
		//Map
		var mapOptions = {
			mapTypeId: google.maps.MapTypeId.ROADMAP
		};
		map = new google.maps.Map(document.getElementById('map-canvas'), mapOptions);
		
		bounds = new google.maps.LatLngBounds();
		coords.clear();
		
		for(i = 0; i<data.coords.length;i++) {
			var pt = new google.maps.LatLng(data.coords[i][1],data.coords[i][0]);
			coords.push(pt);
			bounds.extend(pt);
		}
		map.fitBounds(bounds);
		
		//Arrow Symbol for Path
		var lineSymbol = {
			path: google.maps.SymbolPath.FORWARD_OPEN_ARROW,
			strokeColor: '#000000',
			strokeWeight: 2,
			strokeOpacity: 1.0
		};
		
		//Path
		path = new google.maps.Polyline({
			map: map,
			path: coords,
			strokeColor: '#FF0000',
			strokeOpacity: 1,
			strokeWeight: 2,
			icons: [{
				icon: lineSymbol,
				offset: '100%',
				repeat: '75px',
			}]
		});
		
		//HexOverlay
		hexOverlay.radius = 20;
		
		//OnAdd
		hexOverlay.onAdd = function() {
			
			hexOverlay.layer = d3.select(this.getPanes().overlayMouseTarget).append("div")
				.style("position", "absolute")
			
			//Draw
			hexOverlay.draw = function() {
				var radius = this.radius;
				var buffer = radius*2;
				var projection = this.getProjection();
				var ne = projection.fromLatLngToDivPixel(bounds.getNorthEast());
				var sw = projection.fromLatLngToDivPixel(bounds.getSouthWest());
				var left = sw.x-buffer;
				var top = ne.y-buffer;
				var width = ne.x-sw.x+2*buffer;
				var height = sw.y-ne.y+2*buffer;
				
				//Div Dimensions
				hexOverlay.layer.style("width", width+"px")
				.style("height", height+"px")
				.style("top", top+"px")
				.style("left", left+"px");
				
				//Terrible hack to update the svg
				d3.select("svg").remove()
				
				//Adding svg
				var svg = hexOverlay.layer.append("svg")
				.attr("width", width)
				.attr("height",height)
				
				//Color Gradient
				var color = d3.scale.linear()
				.domain([80, 150])
				.range(["white", "steelblue"])
				.interpolate(d3.interpolateLab);
				
				//Instantiate hexbins
				var hexbin = d3.hexbin()
				.size([width, height])
				.radius(radius);
				
				//Restricts painting region (not exactly sure what this does... yay for copying examples)
				svg.append("clipPath")
					.attr("id", "clip")
				  .append("rect")
					.attr("class", "mesh")
					.attr("width", width)
					.attr("height", height);
				
				//Converting from LatLng to integers
				var points = [];
				for(i = 0; i<coords.length; i++) {
					var pt = projection.fromLatLngToDivPixel(coords.getAt(i));
					points.push([pt.x-left, pt.y-top, cps[i]]);
				}
				
				//Creating the hexes
				if(points.length != 0) {
					var hexes = hexbin(points);
					var temp = svg.append("g")	//Hacking at its finest. There has to be a better way so it can all be chained
						.attr("clip-path", "url(#clip)")
					  .selectAll(".hexagon")
						.data(hexes)
						.enter().append("path")
						.attr("class", "hexagon")
						.attr("d", hexbin.hexagon())
						.attr("transform", function(d) {return "translate(" + d.x + "," + d.y + ")"; })
						.attr("cps", function(d) {
							var total =0;
							for(i=0; i<d.length; i++) {
								total += d[i][2];
							}
							return total/d.length;
						})
						.style("fill-opacity", .6)
						.on("mouseover", function(d) {
							var cps = Number(d3.select(this).attr("cps"))
							showTooltip(d3.event.pageX, d3.event.pageY, "CPS: " + cps.toFixed(2));
						})
						.on("mouseout", function(d) {
							$("#tooltip").remove();
						});
						
						//TODO: These two are placeholder methods. Replace with better behavior 
						google.maps.event.addListener(map,"center_changed", function() {
							$("#tooltip").remove();
						})
						google.maps.event.addListener(map,"center_changed", function() {
							$("#tooltip").remove();
						})
						
						//Fill based on average CPS
						temp.style("fill", color(temp.attr("cps")))
				}
			}
			//onRemove
			hexOverlay.onRemove = function() {
				hexOverlay.layer.remove();
			}
			
			//SetRadius
			hexOverlay.setRadius = function(radius) {
				if(!isNaN(radius) && radius.trim() != "") {
					hexOverlay.radius = radius;
				}
				else {
					alert(radius + " is not a number!")
				}
			}
		}
		hexOverlay.setMap(map);
	});
}

//Tooltip code
function showTooltip(x, y, contents) {
	$('<div id="tooltip">' + contents + '</div>').css( {
		position: 'absolute',
		display: 'none',
		top: y - 25,
		left: x+5,
		border: '1px solid #fdd',
		padding: '2px',
		'background-color': '#fee',
		opacity: 0.80
	}).appendTo("body").fadeIn(200);
}

//Updates the plot
function checkStatus(recenter) {
	
	//RecentLoc
	$.getJSON("/recentloc/",{"start": start, "end": end} , function(data) {
		coords.clear();
		bounds = new google.maps.LatLngBounds();
		for(var i = 0; i<data.coords.length;i++) {
			var pt = new google.maps.LatLng(data.coords[i][1],data.coords[i][0]);
			coords.push(pt);
			bounds.extend(pt);
		}
		console.log(coords.length);
		cps = data.cps;
		
		//Update the overlay
		if(hexOverlay.getMap() != null)
			hexOverlay.draw()
		
		//Recenter the map
		if(map != null && !bounds.isEmpty() && (recenter || realtime == null)) {
			map.fitBounds(bounds);
		}
	});
	
	//Status
    $.getJSON("/status/", function(data) {
        $("#cps").text(data.cps);
        $("#batt").text(data.battery);
        
        $("#time").removeData()
        $("#time").attr("datetime", data.time);
        $("#time").text(data.time);
        $("#time").timeago();
        
        $("#temp").text(data.temp);
        $("#tempf").text(Math.round(data.temp * 1.8 + 32));
        $("#hdop").text(data.hdop);
    }).error(function() { alert("Error connecting to device."); });
    
	//RecentCPS
    $.getJSON("/recentcps/",{"start": start, "end": end}, function(data) {
        cpsplot.setData([{
            threshold: { below: 200, color: "rgb(30, 180, 20)" },
            color: "rgb(200, 20, 30)",
            data: data.cps
        }]);
		//Causes the axes to slide
		if(realtime != null) {
			cpsplot.getOptions().xaxes[0].max = $.now();
			cpsplot.getOptions().xaxes[0].min = $.now()-tdelta;
		}
		else {
			cpsplot.getOptions().xaxes[0].max = null;
			cpsplot.getOptions().xaxes[0].min = null;
		}
        cpsplot.setupGrid();
        cpsplot.draw()
    });
    
	//RecentHDOP
    $.getJSON("/recenthdop/",{"start": start, "end": end}, function(data) {
        hdopplot.setData([{
            threshold: { below: 3, color: "rgb(30, 180, 20)" },
            color: "rgb(200, 20, 30)",
            data: data.hdop
        }]);
		//Causes the axes to slide
		if(realtime != null) {
			hdopplot.getOptions().xaxes[0].max = $.now();
			hdopplot.getOptions().xaxes[0].min = $.now()-tdelta;
		}
		else {
			hdopplot.getOptions().xaxes[0].max = null;
			hdopplot.getOptions().xaxes[0].min = null;
		}
        hdopplot.setupGrid();
        hdopplot.draw()
    });
	
	//RecentHist
	$.getJSON("/recenthist/",{"start": start, "end": end}, function(data) {
        histplot.setData([{
            //threshold: { above: 200, color: "rgb(200, 20, 30)" },
            color: "rgb(30, 180, 20)",
            data: data.hist
        }]);
        histplot.setupGrid();
        histplot.draw()
    });
}

//Used for real time updating
//TODO: Should probably only grab new data instead of grabbing the all the data again (use a queue?)
function update(recenter) {
	$("tooltip").remove();
	start = new Date($.now()-tdelta).toISOString();
	end = new Date().toISOString();
	checkStatus(recenter);
}

/*TODO: Unfixed bug with asynchronous coding
**If you try clearInterval, since checkstatus is async, it will have already started before
**you can stop it
**/
function setTimeBtn() {
	if(realtime == null) {
		start = $('#start').val();
		end = $('#end').val()
		alert("Updating...");
		checkStatus(true);
	}
	else
		alert("Please stop real-time execution first.");
}

//Sets Radius
function setRadiusBtn() {
	hexOverlay.setRadius($('#radius').val());
	hexOverlay.draw();
}

//Toggles Hex Overlay
function toggleHexBtn() {
	hexOverlay.getMap()==null?hexOverlay.setMap(map):hexOverlay.setMap(null);
}

//Toggles Path Visibility
function togglePathBtn() {
	path.getMap()==null?path.setMap(map): path.setMap(null);
}

//Toggles Real Time Updating
function toggleRealBtn() {
	if(realtime == null) {
		update(true);
		realtime = setInterval(update, 2000);
	}
	else {
		clearInterval(realtime);
		realtime = null;
	}
}
